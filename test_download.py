from providers.hailuo_download_provider import HailuoDownloadProvider


provider = HailuoDownloadProvider()

try:
    provider.start()
    provider.open_assets()

    opened = provider.open_latest_video_by_video_element()

    if opened:
        final_file = provider.extract_and_save_video()

        print("\n=== FINAL FILE ===")
        print(final_file)

    input("\nPress ENTER to close...")

except Exception as e:
    print(e)

finally:
    provider.close()