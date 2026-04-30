"""Debug: step-by-step import test to find what hangs"""
import time, sys

def step(name):
    t = time.time()
    sys.stderr.write(f"[{name}] starting...\n")
    sys.stderr.flush()
    return t

def done(name, t):
    ms = int((time.time() - t) * 1000)
    sys.stderr.write(f"[{name}] OK ({ms}ms)\n")
    sys.stderr.flush()

t = step("1. sys/os/time")
import os, json, wave, asyncio, re, uuid, io
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
done("1. sys/os/time", t)

t = step("2. aiohttp")
from aiohttp import web
done("2. aiohttp", t)

t = step("3. grpc")
import grpc
done("3. grpc", t)

t = step("4. google.auth")
import google.auth
done("4. google.auth", t)

t = step("5. google.cloud.texttospeech (v1)")
from google.cloud import texttospeech
done("5. google.cloud.texttospeech (v1)", t)

t = step("6. texttospeech.TextToSpeechClient class")
client_class = texttospeech.TextToSpeechClient
done("6. texttospeech.TextToSpeechClient class", t)

t = step("7. texttospeech.SynthesisInput class")
_ = texttospeech.SynthesisInput
_ = texttospeech.VoiceSelectionParams
_ = texttospeech.AudioConfig
_ = texttospeech.AudioEncoding
done("7. texttospeech types", t)

sys.stderr.write("\n=== ALL IMPORTS OK ===\n")
sys.stderr.flush()
