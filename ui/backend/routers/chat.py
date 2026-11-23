import json
import base64
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..ws.manager import manager
from ..services.ollama import stream_chat, check_health, encode_image_base64
from ..services.director import load_system_prompt, extract_plan_json, validate_and_normalize_plan

router = APIRouter(tags=["chat"])

INPUT_DIR = Path("D:/ai-input")


@router.get("/api/chat/health")
async def chat_health():
    ollama_ok = await check_health()
    return {"ollama": ollama_ok}


@router.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    await manager.connect(ws)
    conversation: list[dict] = []

    try:
        system_prompt = load_system_prompt()
        conversation.append({"role": "system", "content": system_prompt})
    except FileNotFoundError:
        await manager.send(ws, "error", {"message": "Director prompt not found"})
        manager.disconnect(ws)
        return

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            user_text = msg.get("content", "")
            image_name = msg.get("image")  # filename from gallery

            if not user_text.strip() and not image_name:
                continue

            # Build user message for Ollama
            user_msg: dict = {"role": "user", "content": user_text}

            # If image attached, encode for multimodal Gemma
            if image_name:
                img_path = INPUT_DIR / image_name
                if img_path.exists():
                    b64 = encode_image_base64(str(img_path))
                    user_msg["images"] = [b64]
                    # Append image context to text so the LLM knows the filename
                    user_msg["content"] += f"\n\n[Attached image: {image_name}]"
                else:
                    await manager.send(ws, "error", {"message": f"Image not found: {image_name}"})
                    continue

            conversation.append(user_msg)

            # Stream response from Ollama
            full_response = ""
            try:
                async for chunk in stream_chat(conversation):
                    full_response += chunk
                    await manager.send(ws, "chunk", {"content": chunk})
            except Exception as e:
                await manager.send(ws, "error", {"message": f"Ollama error: {e}"})
                # Remove failed user message to keep conversation clean
                conversation.pop()
                continue

            # Store assistant response without images (save memory)
            conversation.append({"role": "assistant", "content": full_response})

            # Strip images from user message after sending (save memory in conversation)
            if "images" in conversation[-2]:
                del conversation[-2]["images"]

            await manager.send(ws, "done", {"content": full_response})

            # Check if response contains a plan
            plan_data = extract_plan_json(full_response)
            if plan_data:
                try:
                    normalized, warnings = validate_and_normalize_plan(plan_data)
                    await manager.send(ws, "plan", {
                        "plan": normalized,
                        "warnings": warnings,
                    })
                except ValueError as e:
                    await manager.send(ws, "plan_error", {"message": str(e)})

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
