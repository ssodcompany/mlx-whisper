from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # 메뉴바 앱 (Dock에 안 보임)
        'CFBundleName': 'VoiceRecorder',
        'CFBundleDisplayName': 'Voice Recorder',
        'CFBundleIdentifier': 'com.voicerecorder.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSMicrophoneUsageDescription': '음성 녹음을 위해 마이크 접근이 필요합니다.',
        'NSAccessibilityUsageDescription': '글로벌 단축키 감지를 위해 접근성 권한이 필요합니다.',
    },
    'packages': ['rumps', 'mlx_whisper', 'mlx', 'torch', 'numpy', 'pynput', 'pyautogui', 'pyperclip'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
