from orchestrators.hailuo_multi_clip_orchestrator import (
    HailuoMultiClipOrchestrator
)


prompts = [
    "Clip 1: A dark abandoned hospital hallway at night, flickering lights, slow camera push forward, VHS horror atmosphere, ultra realistic.",
    "Clip 2: The camera continues deeper into the same hallway, a shadow moves at the end, red emergency light flashes, cinematic tension, ultra realistic.",
    "Clip 3: The shadow suddenly disappears, the camera reaches a half-open door, cold blue light leaks out, disturbing psychological horror mood, ultra realistic."
]


orchestrator = HailuoMultiClipOrchestrator(
    wait_seconds=150
)

files = orchestrator.run(prompts)

print("\n=== DOWNLOADED CLIPS ===")
for f in files:
    print(f)