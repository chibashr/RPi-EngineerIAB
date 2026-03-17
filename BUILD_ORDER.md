# BUILD_ORDER.md

- [ ] 1. Scaffold (Prompt 1)
- [x] 2. CORE agent — module_manager, status_queue, dashboard, /ws/status (Prompt 2)
- [x] 3. SESSION-LIB agent — lib/session_manager.py (Prompt 3)
- [x] 4. MODULE-SERIAL-CAPTURE agent (Prompt 4) [parallel with 5, 6, 7]
- [x] 5. MODULE-REMOTE-CONSOLE agent (Prompt 5) [parallel with 4, 6, 7]
- [x] 6. MODULE-SIMPLE agent (Prompt 6) [parallel with 4, 5, 7]
- [x] 7. FRONTEND agent (Prompt 7) [parallel with 4, 5, 6]
- [x] 8. Integration (Prompt 8)
- [ ] 9. Verify + Finalize (Prompt 9)
