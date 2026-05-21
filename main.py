from core.project_scanner import run_scan
from core.state_writer import ensure_project_brain, append_change_log
from core.project_reader import build_project_summary
from core.task_router import print_project_analysis
from core.handoff_generator import save_handoff

from core.dependency_mapper import DependencyMapper
from core.impact_analyzer import ImpactAnalyzer
from core.orchestrator import Orchestrator

from agents.architect_agent import ArchitectAgent
from agents.memory_agent import MemoryAgent
from agents.coder_agent import CoderAgent
from agents.verifier_agent import VerifierAgent


def show_menu():
    print("")
    print("====================================")
    print("        MODIRAGENT OS - V1")
    print("====================================")
    print("1. Initialize project brain")
    print("2. Scan project and update current_state.md")
    print("3. Show project summary")
    print("4. Run full V1 check")
    print("5. Analyze project and suggest next steps")
    print("6. Generate CHAT_HANDOFF.md")
    print("7. Run Architect Agent")
    print("8. Generate Dependency Map")
    print("9. Analyze Impact")
    print("10. Run Memory Agent")
    print("11. Run Orchestrator")
    print("12. Run Coder Agent")
    print("13. Run Verifier Agent")
    print("Q. Quit")
    print("")


def run_full_check():
    ensure_project_brain(".")
    append_change_log("Project brain checked.")

    report = run_scan(".")

    append_change_log(
        f"Project scanned. "
        f"Folders: {report['total_folders']}, "
        f"Files: {report['total_files']}."
    )

    print("Full V1 check completed.")
    print(f"Folders: {report['total_folders']}")
    print(f"Files: {report['total_files']}")


def run_architect_agent():
    agent = ArchitectAgent(".")
    agent.run()

    append_change_log(
        "ArchitectAgent executed from main menu."
    )


def run_dependency_mapper():
    mapper = DependencyMapper(".")
    mapper.run()

    append_change_log(
        "DependencyMapper executed from main menu."
    )


def run_impact_analyzer():
    changed_file = input(
        "Enter changed file path: "
    ).strip()

    analyzer = ImpactAnalyzer(".")
    analyzer.run(changed_file)

    append_change_log(
        f"ImpactAnalyzer executed for: {changed_file}"
    )


def run_memory_agent():
    agent = MemoryAgent(".")
    agent.run()

    append_change_log(
        "MemoryAgent executed from main menu."
    )


def run_orchestrator():
    goal = input(
        "Enter orchestration goal: "
    ).strip()

    orchestrator = Orchestrator(".")
    orchestrator.run(goal)

    append_change_log(
        f"Orchestrator executed with goal: {goal}"
    )


def run_coder_agent():
    goal = input(
        "Enter coding goal: "
    ).strip()

    agent = CoderAgent(".")
    agent.run(goal)

    append_change_log(
        f"CoderAgent executed with goal: {goal}"
    )


def run_verifier_agent():
    agent = VerifierAgent(".")
    agent.run()

    append_change_log(
        "VerifierAgent executed from main menu."
    )


def main():
    while True:
        show_menu()

        choice = input(
            "Select option: "
        ).strip().lower()

        if choice == "1":
            ensure_project_brain(".")

            append_change_log(
                "Project brain initialized from main menu."
            )

            print("Project brain initialized.")

        elif choice == "2":
            report = run_scan(".")

            append_change_log(
                f"Project scanned from main menu. "
                f"Folders: {report['total_folders']}, "
                f"Files: {report['total_files']}."
            )

            print("Project scan completed.")
            print(f"Folders: {report['total_folders']}")
            print(f"Files: {report['total_files']}")

        elif choice == "3":
            summary = build_project_summary(".")
            print(summary)

        elif choice == "4":
            run_full_check()

        elif choice == "5":
            print_project_analysis(".")

            append_change_log(
                "Project analysis executed from main menu."
            )

        elif choice == "6":
            output = save_handoff(".")

            append_change_log(
                "CHAT_HANDOFF.md generated."
            )

            print(f"Handoff generated: {output}")

        elif choice == "7":
            run_architect_agent()

        elif choice == "8":
            run_dependency_mapper()

        elif choice == "9":
            run_impact_analyzer()

        elif choice == "10":
            run_memory_agent()

        elif choice == "11":
            run_orchestrator()

        elif choice == "12":
            run_coder_agent()

        elif choice == "13":
            run_verifier_agent()

        elif choice == "q":
            print("Goodbye.")
            break

        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()