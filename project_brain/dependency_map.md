# DEPENDENCY MAP

Generated at: 2026-05-26 22:30:42

## full_selfcare_factory.py

- core.content_series_planner
- core.selfcare_content_engine
- core.timeline_engine
- engines.viral_hook_engine
- orchestrators.hailuo_multi_clip_orchestrator
- pathlib
- providers.elevenlabs_voice_provider
- utils.ffmpeg_clip_audio_merger
- utils.final_cinematic_assembler

## main.py

- agents.architect_agent
- agents.coder_agent
- agents.memory_agent
- agents.verifier_agent
- core.dependency_mapper
- core.handoff_generator
- core.impact_analyzer
- core.orchestrator
- core.project_reader
- core.project_scanner
- core.state_writer
- core.task_router

## postprocess_existing_video.py

- engines.music_engine
- engines.subtitle_burner
- engines.subtitle_engine

## rebuild_existing_project.py

- engines.audio_finish_engine
- engines.ingredient_overlay_engine
- engines.music_engine
- engines.subtitle_burner
- engines.subtitle_engine
- pathlib
- utils.ffmpeg_clip_audio_merger
- utils.final_cinematic_assembler

## test_audio_video_merge.py

- utils.ffmpeg_audio_merger

## test_browser.py

- automation.browser_manager

## test_clip_audio_sync.py

- pathlib
- utils.ffmpeg_clip_audio_merger

## test_content_series_planner.py

- core.content_series_planner

## test_continuity_engine.py

- core.continuity_engine

## test_continuity_hailuo_pipeline.py

- core.continuity_engine
- orchestrators.hailuo_multi_clip_orchestrator

## test_download.py

- providers.hailuo_download_provider

## test_elevenlabs_voice.py

- providers.elevenlabs_voice_provider

## test_episode_preview.py

- core.content_series_planner
- core.selfcare_content_engine
- full_selfcare_factory

## test_ffmpeg_stitch.py

- pathlib
- utils.ffmpeg_stitcher

## test_final_cinematic_assembly.py

- pathlib
- utils.final_cinematic_assembler

## test_full_ai_video_pipeline.py

- core.content_series_planner
- core.selfcare_content_engine
- core.timeline_engine
- core.topic_memory_engine
- core.video_provider_router
- datetime
- dotenv
- engines.ai_director_engine
- engines.ai_memory_learning_engine
- engines.ai_performance_analyzer
- engines.audio_finish_engine
- engines.auto_optimization_loop_engine
- engines.auto_publishing_engine
- engines.hook_overlay_engine
- engines.ingredient_overlay_engine
- engines.music_engine
- engines.scene_continuity_engine
- engines.seo_package_engine
- engines.subtitle_burner
- engines.subtitle_engine
- engines.thumbnail_engine
- engines.viral_hook_engine
- json
- os
- pathlib
- providers.elevenlabs_voice_provider
- providers.suno_music_provider
- random
- utils.ffmpeg_clip_audio_merger
- utils.final_cinematic_assembler

## test_full_hailuo_pipeline.py

- core.continuity_engine
- orchestrators.hailuo_multi_clip_orchestrator

## test_hailuo.py

- providers.hailuo_browser_provider
- time

## test_multi_clip.py

- orchestrators.hailuo_multi_clip_orchestrator

## test_openai_trends.py

- providers.openai_trend_provider

## test_runway_orchestrator_direct.py

- orchestrators.runway_browser_orchestrator

## test_selfcare_content_engine.py

- core.selfcare_content_engine

## test_selfcare_voice.py

- core.selfcare_content_engine
- providers.elevenlabs_voice_provider

## test_timeline_engine.py

- core.timeline_engine

## test_timeline_voice.py

- core.timeline_engine
- pathlib
- providers.elevenlabs_voice_provider

## agents\architect_agent.py

- datetime
- pathlib

## agents\change_request_agent.py

- datetime

## agents\coder_agent.py

- datetime
- pathlib

## agents\code_generation_agent.py

- agents.project_context_agent
- datetime

## agents\memory_agent.py

- datetime
- pathlib

## agents\project_context_agent.py

- ast
- pathlib

## agents\project_upgrade_agent.py

- datetime
- pathlib
- sys

## agents\self_editing_agent.py

- agents.change_request_agent
- agents.code_generation_agent
- agents.project_upgrade_agent
- agents.verifier_agent
- argparse
- core.dependency_graph_engine
- core.upgrade_planner_engine
- execution.apply_patch_engine
- execution.patch_preview_engine
- execution.patch_validator

## agents\seo_agent.py

- datetime
- json
- pathlib

## agents\trend_agent.py

- datetime
- json
- pathlib

## agents\verifier_agent.py

- datetime
- pathlib

## agents\__init__.py

- No imports detected

## automation\browser_manager.py

- os
- playwright.sync_api

## config\config_loader.py

- pathlib
- yaml

## config\__init__.py

- No imports detected

## core\config_injection_engine.py

- config.config_loader

## core\content_series_planner.py

- dataclasses
- typing

## core\continuity_engine.py

- dataclasses
- typing

## core\dependency_graph_engine.py

- datetime
- pathlib
- re
- sys

## core\dependency_mapper.py

- datetime
- pathlib
- re

## core\full_project_scanner.py

- datetime
- os
- pathlib

## core\handoff_generator.py

- datetime
- pathlib

## core\impact_analyzer.py

- core.dependency_mapper
- datetime
- pathlib

## core\live_handoff_engine.py

- datetime
- pathlib

## core\master_orchestrator_engine.py

- datetime
- json
- pathlib

## core\orchestrator.py

- core.project_reader
- datetime
- pathlib

## core\project_brain_engine.py

- ast
- datetime
- os
- pathlib

## core\project_reader.py

- pathlib

## core\project_scanner.py

- datetime
- pathlib

## core\provider_registry_engine.py

- dotenv
- json
- os
- pathlib

## core\safety_guard.py

- pathlib

## core\selfcare_content_engine.py

- dataclasses
- engines.visual_scenario_engine

## core\state_writer.py

- datetime
- pathlib

## core\task_router.py

- datetime
- pathlib

## core\timeline_engine.py

- dataclasses
- typing

## core\topic_memory_engine.py

- datetime
- json
- pathlib

## core\upgrade_planner_engine.py

- datetime
- pathlib

## core\video_provider_router.py

- core.provider_registry_engine
- orchestrators.hailuo_multi_clip_orchestrator
- orchestrators.runway_browser_orchestrator
- providers.minimax_video_provider
- providers.runway_video_provider

## core\__init__.py

- No imports detected

## dashboard\control_center.py

- json
- pathlib

## engines\ai_director_engine.py

- json
- pathlib
- random

## engines\ai_memory_learning_engine.py

- datetime
- json
- pathlib

## engines\ai_performance_analyzer.py

- json
- pathlib
- random

## engines\audio_finish_engine.py

- pathlib
- subprocess

## engines\audio_sync_engine.py

- pathlib
- utils.ffmpeg_clip_audio_merger

## engines\auto_optimization_loop_engine.py

- json
- pathlib

## engines\auto_publishing_engine.py

- datetime
- json
- pathlib

## engines\cinematic_motion_engine.py

- random

## engines\final_assembly_engine.py

- utils.final_cinematic_assembler

## engines\hook_overlay_engine.py

- pathlib
- subprocess

## engines\ingredient_overlay_engine.py

- pathlib
- subprocess

## engines\intro_thumbnail_frame_engine.py

- pathlib
- subprocess

## engines\music_engine.py

- core.config_injection_engine
- pathlib
- subprocess

## engines\narration_engine.py

- pathlib
- providers.elevenlabs_voice_provider

## engines\scene_continuity_engine.py

- json
- pathlib

## engines\seo_package_engine.py

- json
- pathlib
- random

## engines\smart_transition_engine.py

- pathlib
- subprocess
- tempfile

## engines\subtitle_burner.py

- pathlib
- subprocess

## engines\subtitle_engine.py

- pathlib
- re

## engines\thumbnail_engine.py

- PIL
- pathlib
- subprocess

## engines\trend_engine.py

- random

## engines\trend_research_engine.py

- datetime
- random

## engines\video_generation_engine.py

- core.video_provider_router

## engines\video_prompt_engine.py

- core.selfcare_content_engine
- engines.ai_director_engine
- engines.scene_continuity_engine

## engines\viral_hook_engine.py

- random

## engines\visual_scenario_engine.py

- engines.cinematic_motion_engine
- random

## execution\apply_patch_engine.py

- execution.approval_engine
- execution.patch_validator
- execution.safe_code_editor

## execution\approval_engine.py

- datetime
- pathlib

## execution\command_runner.py

- pathlib
- subprocess

## execution\patch_preview_engine.py

- datetime
- difflib
- pathlib

## execution\patch_validator.py

- ast
- pathlib

## execution\rollback_manager.py

- datetime
- pathlib
- shutil

## execution\safe_code_editor.py

- datetime
- pathlib
- shutil

## execution\__init__.py

- No imports detected

## orchestrators\hailuo_multi_clip_orchestrator.py

- providers.hailuo_browser_provider
- providers.hailuo_download_provider
- time

## orchestrators\runway_browser_orchestrator.py

- providers.runway_browser_provider
- providers.runway_download_provider
- time

## pipelines\full_video_pipeline.py

- core.content_series_planner
- core.timeline_engine
- core.topic_memory_engine
- core.video_provider_router
- datetime
- dotenv
- engines.ai_memory_learning_engine
- engines.ai_performance_analyzer
- engines.audio_finish_engine
- engines.audio_sync_engine
- engines.auto_optimization_loop_engine
- engines.auto_publishing_engine
- engines.final_assembly_engine
- engines.hook_overlay_engine
- engines.ingredient_overlay_engine
- engines.music_engine
- engines.narration_engine
- engines.seo_package_engine
- engines.subtitle_burner
- engines.subtitle_engine
- engines.thumbnail_engine
- engines.trend_engine
- engines.video_generation_engine
- engines.video_prompt_engine
- engines.viral_hook_engine
- os
- pathlib
- providers.suno_music_provider
- sys
- utils.ffmpeg_clip_audio_merger
- utils.final_cinematic_assembler

## pipelines\__init__.py

- No imports detected

## providers\elevenlabs_voice_provider.py

- dotenv
- os
- pathlib
- requests

## providers\hailuo_browser_provider.py

- automation.browser_manager
- time

## providers\hailuo_download_provider.py

- automation.browser_manager
- base64
- pathlib
- time

## providers\minimax_video_provider.py

- dotenv
- os

## providers\openai_provider.py

- dotenv
- os

## providers\openai_trend_provider.py

- dotenv
- openai
- os

## providers\runway_browser_provider.py

- automation.browser_manager
- time

## providers\runway_download_provider.py

- automation.browser_manager
- pathlib
- requests
- time

## providers\runway_video_provider.py

- dotenv
- os
- pathlib
- requests
- time

## providers\__init__.py

- No imports detected

## ui\app.py

- datetime
- dotenv
- json
- os
- pathlib
- queue
- shutil
- signal
- subprocess
- sys
- threading
- time
- tkinter
- ui.components.progress_tracker
- ui.services.env_service
- ui.services.runner_service
- zipfile

## ui\app_backup_before_refactor.py

- datetime
- dotenv
- json
- os
- pathlib
- shutil
- subprocess
- sys
- threading
- tkinter
- zipfile

## ui\components\progress_tracker.py

- No imports detected

## ui\components\__init__.py

- No imports detected

## ui\services\env_service.py

- dotenv
- os
- pathlib

## ui\services\runner_service.py

- subprocess

## ui\services\__init__.py

- No imports detected

## ui\tabs\__init__.py

- No imports detected

## utils\download_helper.py

- os
- pathlib
- time

## utils\ffmpeg_audio_merger.py

- pathlib
- shutil
- subprocess

## utils\ffmpeg_clip_audio_merger.py

- pathlib
- subprocess

## utils\ffmpeg_stitcher.py

- pathlib
- shutil
- subprocess

## utils\final_cinematic_assembler.py

- pathlib
- subprocess
