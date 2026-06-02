from pathlib import Path
from datetime import datetime
import json
import uuid


class RuntimeStateManager:

    """
    Runtime State Manager V1

    Purpose:
    - Persist execution state
    - Track queue progress
    - Track approval stop points
    - Track rollback history
    - Support future resume/recover mode

    This module does not execute patches.
    It only saves and loads runtime state.
    """

    def __init__(self, project_root="."):

        self.project_root = Path(project_root).resolve()

        self.state_dir = (
            self.project_root
            / "project_brain"
            / "runtime_state"
        )

        self.state_dir.mkdir(
            parents=True,
            exist_ok=True
        )

    def create_session_id(self):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        short_id = uuid.uuid4().hex[:8]

        return f"runtime_{timestamp}_{short_id}"

    def build_initial_state(
        self,
        goal,
        orchestration_plan
    ):

        session_id = self.create_session_id()

        return {
            "session_id": session_id,
            "created_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "updated_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "goal": goal,
            "status": "CREATED",
            "current_step": None,
            "completed_steps": [],
            "failed_step": None,
            "approval_required": False,
            "approval_granted": False,
            "orchestration_plan": orchestration_plan,
            "execution_log": [],
            "rollback_history": [],
        }

    def get_state_path(self, session_id):

        return self.state_dir / f"{session_id}.json"

    def save_state(self, state):

        state["updated_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        session_id = state["session_id"]
        path = self.get_state_path(session_id)

        path.write_text(
            json.dumps(
                state,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return str(path)

    def load_state(self, session_id):

        path = self.get_state_path(session_id)

        if not path.exists():
            raise FileNotFoundError(
                f"Runtime state not found: {path}"
            )

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    def update_step(
        self,
        state,
        step,
        action,
        status,
        message="",
        action_context=None
    ):

        if action_context is None:
            action_context = {}

        state["current_step"] = {
            "step": step,
            "action": action,
            "status": status,
            "message": message,
            "action_context": action_context,
        }

        state["execution_log"].append({
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "step": step,
            "action": action,
            "status": status,
            "message": message,
            "action_context": action_context,
        })

        if status == "SUCCESS":

            state["completed_steps"].append({
                "step": step,
                "action": action,
            })

        if status == "FAILED":

            state["failed_step"] = {
                "step": step,
                "action": action,
                "message": message,
                "action_context": action_context,
            }

            state["status"] = "FAILED"

        if status == "WAITING_APPROVAL":

            state["approval_required"] = True
            state["status"] = "WAITING_APPROVAL"

        return state

    def mark_running(self, state):

        state["status"] = "RUNNING"
        return state

    def mark_complete(self, state):

        state["status"] = "COMPLETE"
        return state

    def mark_approval_granted(self, state):

        state["approval_granted"] = True
        state["approval_required"] = False
        state["status"] = "APPROVED"
        return state

    def add_rollback_entry(
        self,
        state,
        rollback_action,
        target,
        result
    ):

        state["rollback_history"].append({
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "rollback_action": rollback_action,
            "target": target,
            "result": result,
        })

        return state

    def list_sessions(self):

        sessions = []

        for path in self.state_dir.glob("*.json"):

            try:
                data = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )

                sessions.append({
                    "session_id": data.get(
                        "session_id"
                    ),
                    "status": data.get(
                        "status"
                    ),
                    "goal": data.get(
                        "goal"
                    ),
                    "updated_at": data.get(
                        "updated_at"
                    ),
                    "path": str(path),
                })

            except Exception:

                continue

        sessions.sort(
            key=lambda item: item.get(
                "updated_at",
                ""
            ),
            reverse=True
        )

        return sessions


if __name__ == "__main__":

    manager = RuntimeStateManager(".")

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
                "rollback_action": "RESTORE_BACKUP",
                "target": "providers/runway_video_provider.py"
            }
        ]
    }

    state = manager.build_initial_state(
        goal="test runtime state",
        orchestration_plan=orchestration_plan
    )

    state = manager.mark_running(state)

    state = manager.update_step(
        state,
        step=1,
        action="EXTRACT_FUNCTION",
        status="SUCCESS",
        message="Function extracted"
    )

    state = manager.update_step(
        state,
        step=2,
        action="BUILD_DIFF",
        status="SUCCESS",
        message="Diff built"
    )

    state = manager.update_step(
        state,
        step=3,
        action="REQUEST_APPROVAL",
        status="WAITING_APPROVAL",
        message="User approval required"
    )

    path = manager.save_state(state)

    print("\n" + "=" * 60)
    print("RUNTIME STATE SAVED")
    print("=" * 60)

    print("")
    print(f"Session: {state['session_id']}")
    print(f"Status: {state['status']}")
    print(f"Path: {path}")

    print("\n" + "=" * 60)
    print("LATEST SESSIONS")
    print("=" * 60)

    for session in manager.list_sessions()[:5]:

        print("")
        print(f"Session: {session['session_id']}")
        print(f"Status: {session['status']}")
        print(f"Goal: {session['goal']}")