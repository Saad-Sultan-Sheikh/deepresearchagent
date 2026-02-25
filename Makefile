.PHONY: all agents tests evaluators eval

VENV=venv/bin/python

all: tests evaluators
	@echo "🎉 Full pipeline completed successfully"

agents:
	@echo "▶ Running agents in parallel..."
	$(VENV) -m src.agent.runner --persona persona_001 & \
	$(VENV) -m src.agent.runner --persona persona_002 & \
	$(VENV) -m src.agent.runner --persona persona_003 & \
	wait
	@echo "✔ Agents finished"

tests:
	@echo "▶ Running test suite..."
	$(VENV) -m pytest tests/ -v
	@echo "✔ Tests passed"

evaluators: agents
	@echo "▶ Running evaluators in parallel..."
	$(VENV) -m src.evaluation.evaluator --persona persona_001 & \
	$(VENV) -m src.evaluation.evaluator --persona persona_002 & \
	$(VENV) -m src.evaluation.evaluator --persona persona_003 & \
	wait
	@echo "✔ Evaluators finished"

eval:
	@echo "▶ Running evaluators in parallel..."
	$(VENV) -m src.evaluation.evaluator --persona persona_001 & \
	$(VENV) -m src.evaluation.evaluator --persona persona_002 & \
	$(VENV) -m src.evaluation.evaluator --persona persona_003 & \
	wait
	@echo "✔ Evaluators finished"
