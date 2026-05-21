from providers.hailuo_browser_provider import HailuoBrowserProvider
import time


provider = HailuoBrowserProvider()

try:
    provider.start()
    provider.open_hailuo()

    provider.fill_prompt(
        "A dark cinematic abandoned hallway, flickering red emergency lights, VHS horror atmosphere, slow camera push forward, ultra realistic."
    )

    time.sleep(1)

    provider.click_create()

    print("\nGeneration command sent.")
    input("Check if generation started, then press ENTER...")

except Exception as e:
    print("\nTEST FAILED:")
    print(e)

finally:
    provider.close()