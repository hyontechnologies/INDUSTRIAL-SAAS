import asyncio
import websockets
import json


async def test_ws():
    uri = "ws://localhost:8000/api/v1/ws/piccadily/PICCADILY_PLANT_01?api_key=changeme"
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as ws:
            print("Connected! Waiting for snapshot...")
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"Received message type: {data.get('type')}")
            print(f"Snapshot keys: {list(data.keys())}")
            if "data" in data:
                print(f"Number of tags in snapshot: {len(data['data'])}")
                first_tag = list(data["data"].keys())[0]
                print(f"Sample tag ({first_tag}): {data['data'][first_tag]}")

            print("Waiting for live update (3 seconds)...")
            try:
                update = await asyncio.wait_for(ws.recv(), timeout=3.0)
                udata = json.loads(update)
                print(f"Received live update type: {udata.get('type')}")
            except asyncio.TimeoutError:
                print("No live update received within 3 seconds.")
    except Exception as e:
        print(f"Connection failed: {e}")


asyncio.run(test_ws())
