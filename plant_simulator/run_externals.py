import sys
import subprocess
import time
import threading

# Colored output helpers
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

processes = []
stop_event = threading.Event()


def log_stream(proc, prefix, color):
    """Read a process output stream and print with a prefix."""
    try:
        for line in iter(proc.stdout.readline, b""):
            if stop_event.is_set():
                break
            decoded = line.decode("utf-8", errors="ignore").strip()
            if decoded:
                print(f"{color}{prefix}{RESET} | {decoded}")
    except Exception as exc:
        print(f"Error reading {prefix} stream: {exc}")
    finally:
        proc.stdout.close()


def main():
    print("=" * 70)
    print("   Piccadily Industrial Historian Pipeline Orchestrator")
    print("   Starting Simulator, Bridge, and Edge Agent simultaneously...")
    print("=" * 70)

    # 1. Start Modbus Simulator
    print(f"\n{GREEN}[SYSTEM]{RESET} Starting Modbus Simulator (PLC)...")
    sim_proc = subprocess.Popen(
        [sys.executable, "-u", "plant_simulator/piccadily_boiler_simulator.py", "--port", "5022"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append((sim_proc, "SIMULATOR", GREEN))
    threading.Thread(target=log_stream, args=(sim_proc, "SIMULATOR", GREEN), daemon=True).start()

    # Wait for Modbus server to bind
    time.sleep(3)

    # 2. Start OPC UA Bridge
    print(f"\n{BLUE}[SYSTEM]{RESET} Starting OPC UA Bridge...")
    bridge_proc = subprocess.Popen(
        [sys.executable, "-u", "plant_simulator/piccadily_opcua_bridge.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append((bridge_proc, "BRIDGE", BLUE))
    threading.Thread(target=log_stream, args=(bridge_proc, "BRIDGE", BLUE), daemon=True).start()

    # Wait for OPC UA server to start
    time.sleep(4)

    # 3. Start Edge Agent
    print(f"\n{CYAN}[SYSTEM]{RESET} Starting OPC UA Edge Agent...")
    agent_proc = subprocess.Popen(
        [sys.executable, "-u", "edge-agent/edge_agent.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    processes.append((agent_proc, "EDGE_AGENT", CYAN))
    threading.Thread(target=log_stream, args=(agent_proc, "EDGE_AGENT", CYAN), daemon=True).start()

    print(
        f"\n{GREEN}[SYSTEM]{RESET} All three systems running simultaneously. Press Ctrl+C to terminate all processes."
    )
    print("=" * 70)

    # Wait loop
    try:
        while True:
            # Check if any process has terminated early
            for proc, name, color in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n{RED}[SYSTEM]{RESET} Process {color}{name}{RESET} exited with code {ret}")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{RED}[SYSTEM]{RESET} Shutting down pipeline. Terminating children...")
        stop_event.set()

        # Terminate all processes
        for proc, name, _ in processes:
            try:
                proc.terminate()
            except Exception:
                pass

        # Wait a brief moment and force kill if still running
        time.sleep(2)
        for proc, name, _ in processes:
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        print(f"{GREEN}[SYSTEM]{RESET} Shutdown complete.")


if __name__ == "__main__":
    main()
