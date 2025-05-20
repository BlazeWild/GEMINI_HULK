#!/bin/bash
curl -X POST "http://localhost:8000/runs/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant": {
      "id": "agent"
    },
    "input": {
      "message": [
        {
          "role": "user",
          "content": "When was LangGraph Cloud released?"
        }
      ]
    },
    "metadata": {},
    "config": {
      "configurable": {}
    },
    "multitask_strategy": "reject"
  }'
