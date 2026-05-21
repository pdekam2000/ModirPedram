from orchestrators.runway_browser_orchestrator import RunwayBrowserOrchestrator

prompts = [
    """
    A cinematic woman applying skincare cream in a bright luxury bathroom,
    soft natural light, realistic skin texture, beauty commercial,
    professional camera movement, 10 second video.
    """,

    """
    Close-up skincare product on marble table,
    water drops, luxury cosmetic advertisement,
    shallow depth of field, premium beauty commercial,
    cinematic lighting, 10 second video.
    """,

    """
    Woman looking into mirror after skincare routine,
    healthy glowing skin, elegant bathroom,
    cinematic beauty ad, realistic motion,
    professional commercial style, 10 second video.
    """
]

runner = RunwayBrowserOrchestrator(
    wait_seconds=20
)

result = runner.run(prompts)

print("\nRESULT:")
print(result)