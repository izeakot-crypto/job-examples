# Voice Assistants Gateway

A gateway for connecting voice assistants to the LIRA telephony platform.

## What I built
- Built an abstraction layer over multiple assistant providers.
- Added session management for conversations during phone calls.
- Integrated the gateway with the telephony platform through FastAPI.

## Stack
- Python, FastAPI, Pydantic.
- OpenAI API, Anthropic API, n8n Webhooks.
- Provider Factory pattern.

## Result
- A single gateway for multiple voice assistant scenarios.
- Conversation continuity across a single session.
- Easier onboarding of new providers.
