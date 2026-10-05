from server.agents.orchestrator import AgentOrchestrator
class MockKG: pass
class MockSession: pass
orch = AgentOrchestrator(MockKG(), MockSession())
print(orch._classify_intent("I need help brainstorming a new hackathon project."))
