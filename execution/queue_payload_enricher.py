from copy import deepcopy


class QueuePayloadEnricher:

    """
    Queue Payload Enricher V1

    Purpose:
    - Inject target_file / target_function into queue items
    - Inject patch_data into orchestration_plan
    - Keep runtime state non-null and UI-ready
    """

    def enrich_queue(
        self,
        queue,
        patch_data
    ):

        enriched_queue = []

        target_file = patch_data.get(
            "target_file"
        )

        target_function = (
            patch_data.get("function_name")
            or patch_data.get("target_function")
        )

        class_name = patch_data.get(
            "class_name"
        )

        for item in queue:

            new_item = deepcopy(item)

            if not new_item.get("target_file"):
                new_item["target_file"] = target_file

            if not new_item.get("target_function"):
                new_item["target_function"] = target_function

            if not new_item.get("class_name"):
                new_item["class_name"] = class_name

            enriched_queue.append(new_item)

        return enriched_queue

    def enrich_plan(
        self,
        orchestration_plan,
        patch_data
    ):

        plan = deepcopy(orchestration_plan)

        plan["patch_data"] = patch_data

        plan["queue"] = self.enrich_queue(
            queue=plan.get("queue", []),
            patch_data=patch_data
        )

        return plan


if __name__ == "__main__":

    enricher = QueuePayloadEnricher()

    orchestration_plan = {
        "queue": [
            {
                "step": 1,
                "action": "EXTRACT_FUNCTION"
            },
            {
                "step": 2,
                "action": "BUILD_DIFF"
            },
            {
                "step": 3,
                "action": "REQUEST_APPROVAL"
            }
        ],
        "rollback_strategy": [
            {
                "rollback_action": "RESTORE_BACKUP"
            }
        ]
    }

    patch_data = {
        "operation": "REPLACE_FUNCTION",
        "target_file": "providers/runway_video_provider.py",
        "function_name": "retry_generation",
        "class_name": None,
        "code": "def retry_generation(...): pass",
        "diff_preview": "--- old\n+++ new"
    }

    enriched = enricher.enrich_plan(
        orchestration_plan=orchestration_plan,
        patch_data=patch_data
    )

    print("\n" + "=" * 60)
    print("QUEUE PAYLOAD ENRICHER TEST")
    print("=" * 60)

    print("")
    print(enriched)