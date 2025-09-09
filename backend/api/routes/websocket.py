"""
WebSocket endpoints for real-time communication.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...logging_config import get_logger

router = APIRouter()
logger = get_logger("websocket")


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job updates."""
    from ...utils.websocket_manager import get_websocket_manager

    ws_manager = get_websocket_manager()
    client_info = {
        'client_host': getattr(websocket.client, 'host', 'unknown') if websocket.client else 'unknown',
        'user_agent': websocket.headers.get('user-agent', 'unknown')
    }

    # Add connection to manager
    ws_manager.add_connection(job_id, websocket, client_info)

    await websocket.accept()

    # Send the current job state immediately if exists
    try:
        from ...job_queue_unified import get_job_queue
        job_queue = get_job_queue()
        current_status = job_queue.get_job_status(job_id)
        if current_status:
            await websocket.send_json(current_status)
    except Exception as e:
        logger.warning(f"Failed to send initial job status for {job_id}: {e}")

    try:
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await websocket.receive_text()
                # Echo back for ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error for job {job_id}: {e}")
                break
    finally:
        # Clean up connection
        ws_manager.remove_connection(job_id, websocket)
