import rumps
import pyaudio
import numpy as np
import threading
import tempfile
import wave
import json
import os
from pathlib import Path

import mlx_whisper
import pyperclip
import pyautogui
from pynput import keyboard


class VoiceRecorderApp(rumps.App):
    def __init__(self):
        super().__init__("🎤", quit_button=None)
        
        # 설정 로드
        self.config_path = Path.home() / ".config" / "voice-recorder" / "config.json"
        self.load_config()
        
        # 오디오 설정
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.CHUNK = 1024
        
        self.is_recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.record_thread = None
        
        # 단축키 리스너
        self.hotkey_listener = None
        self.setup_hotkey()
        
        # 메뉴 구성
        self.build_menu()
    
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            "hotkey": "cmd+shift+space",
            "language": "ko",
            "model": "mlx-community/whisper-large-v3-turbo"
        }
        
        try:
            if self.config_path.exists():
                with open(self.config_path, "r") as f:
                    self.config = {**default_config, **json.load(f)}
            else:
                self.config = default_config
        except:
            self.config = default_config
    
    def save_config(self):
        """설정 파일 저장"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)
    
    def build_menu(self):
        """메뉴 구성"""
        self.menu.clear()
        
        # 녹음 상태
        status = "🔴 녹음 중지" if self.is_recording else "녹음 시작"
        self.status_item = rumps.MenuItem(
            f"{status} ({self.format_hotkey(self.config['hotkey'])})",
            callback=self.toggle_recording
        )
        self.menu.add(self.status_item)
        
        self.menu.add(rumps.separator)
        
        # 단축키 설정
        hotkey_menu = rumps.MenuItem("단축키 설정")
        hotkeys = [
            ("cmd+shift+space", "⌘⇧Space"),
            ("cmd+shift+r", "⌘⇧R"),
            ("alt+space", "⌥Space"),
            ("cmd+alt+space", "⌘⌥Space"),
            ("ctrl+shift+space", "⌃⇧Space"),
        ]
        for key, label in hotkeys:
            item = rumps.MenuItem(
                f"{'✓ ' if self.config['hotkey'] == key else '   '}{label}",
                callback=lambda sender, k=key: self.set_hotkey(k)
            )
            hotkey_menu.add(item)
        self.menu.add(hotkey_menu)
        
        # 언어 설정
        lang_menu = rumps.MenuItem("언어")
        languages = [("ko", "한국어"), ("en", "English"), ("ja", "日本語"), ("zh", "中文")]
        for code, name in languages:
            item = rumps.MenuItem(
                f"{'✓ ' if self.config['language'] == code else '   '}{name}",
                callback=lambda sender, c=code: self.set_language(c)
            )
            lang_menu.add(item)
        self.menu.add(lang_menu)
        
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("종료", callback=self.quit_app))
    
    def format_hotkey(self, hotkey):
        """단축키를 보기 좋게 포맷"""
        replacements = {
            "cmd": "⌘", "shift": "⇧", "alt": "⌥", 
            "ctrl": "⌃", "space": "Space", "+": ""
        }
        result = hotkey
        for k, v in replacements.items():
            result = result.replace(k, v)
        return result
    
    def parse_hotkey_for_pynput(self, hotkey):
        """pynput용 단축키 파싱"""
        parts = hotkey.lower().split("+")
        keys = set()
        for part in parts:
            if part == "cmd":
                keys.add(keyboard.Key.cmd)
            elif part == "shift":
                keys.add(keyboard.Key.shift)
            elif part == "alt":
                keys.add(keyboard.Key.alt)
            elif part == "ctrl":
                keys.add(keyboard.Key.ctrl)
            elif part == "space":
                keys.add(keyboard.Key.space)
            elif len(part) == 1:
                keys.add(keyboard.KeyCode.from_char(part))
        return keys
    
    def setup_hotkey(self):
        """글로벌 단축키 설정"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        
        target_keys = self.parse_hotkey_for_pynput(self.config["hotkey"])
        current_keys = set()
        
        def on_press(key):
            current_keys.add(key)
            if target_keys.issubset(current_keys):
                self.toggle_recording(None)
        
        def on_release(key):
            current_keys.discard(key)
        
        self.hotkey_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.hotkey_listener.start()
    
    def set_hotkey(self, hotkey):
        """단축키 변경"""
        self.config["hotkey"] = hotkey
        self.save_config()
        self.setup_hotkey()
        self.build_menu()
        rumps.notification("음성 인식", "", f"단축키가 {self.format_hotkey(hotkey)}로 변경되었습니다.")
    
    def set_language(self, lang):
        """언어 변경"""
        self.config["language"] = lang
        self.save_config()
        self.build_menu()
        lang_names = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "中文"}
        rumps.notification("음성 인식", "", f"언어가 {lang_names[lang]}로 변경되었습니다.")
    
    def toggle_recording(self, sender):
        """녹음 토글"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()
    
    def start_recording(self):
        """녹음 시작"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.frames = []
        self.title = "🔴"
        self.build_menu()
        
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        def record():
            while self.is_recording:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    self.frames.append(data)
                except:
                    break
        
        self.record_thread = threading.Thread(target=record, daemon=True)
        self.record_thread.start()
    
    def stop_recording(self):
        """녹음 중지 및 전사"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self.title = "⏳"
        
        if self.record_thread:
            self.record_thread.join(timeout=1)
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        if not self.frames:
            self.title = "🎤"
            self.build_menu()
            return
        
        # 별도 스레드에서 전사 처리
        threading.Thread(target=self.transcribe_and_paste, daemon=True).start()
    
    def transcribe_and_paste(self):
        """전사 및 붙여넣기"""
        try:
            # WAV 파일로 저장
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                wf = wave.open(temp_path, 'wb')
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
            
            # mlx-whisper로 전사
            result = mlx_whisper.transcribe(
                temp_path,
                path_or_hf_repo=self.config["model"],
                language=self.config["language"]
            )
            text = result["text"].strip()
            
            # 임시 파일 삭제
            os.unlink(temp_path)
            
            if text:
                # 클립보드에 복사
                pyperclip.copy(text)
                
                # 현재 위치에 붙여넣기 (약간의 딜레이)
                threading.Timer(0.1, lambda: pyautogui.hotkey("command", "v")).start()
                
                rumps.notification("음성 인식 완료", "", text[:50] + ("..." if len(text) > 50 else ""))
            else:
                rumps.notification("음성 인식", "", "인식된 텍스트가 없습니다.")
        
        except Exception as e:
            rumps.notification("오류", "", str(e)[:100])
        
        finally:
            self.title = "🎤"
            self.frames = []
            self.build_menu()
    
    def quit_app(self, sender):
        """앱 종료"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.stream:
            self.stream.close()
        self.audio.terminate()
        rumps.quit_application()


if __name__ == "__main__":
    app = VoiceRecorderApp()
    app.run()
