import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import glob


def create_temp_directory():
    """创建临时目录并返回路径"""
    return tempfile.mkdtemp()


def cleanup_temp_files(temp_dir):
    """清理临时文件"""
    shutil.rmtree(temp_dir)
    print("临时文件已清理")


def separate_audio(audio_file, output_dir):
    """
    使用demucs分离音频
    
    参数:
        audio_file: 原始音频文件路径
        output_dir: demucs输出目录
        
    返回:
        demucs输出目录路径
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 运行demucs命令 - 使用--mp3参数输出MP3格式而不是WAV格式
    demucs_cmd = [
        "demucs", 
        "--out", output_dir,
        "--mp3",  # 使用MP3格式输出
        "-n", "mdx_extra_q",  # 使用推荐的模型
        audio_file
    ] 
    subprocess.run(demucs_cmd, check=True)
    
    return output_dir


def find_audio_tracks(base_dir, audio_name):
    """
    查找分离出的音频文件
    
    参数:
        base_dir: demucs输出的基础目录
        audio_name: 音频文件名（不含扩展名）
        
    返回:
        包含各轨道路径的字典
    """
    model_name = "mdx_extra_q"  # 使用的模型名
    
    # 在输出目录中查找可能的文件
    print(f"查找输出目录: {base_dir}")
    if os.path.exists(base_dir):
        print(f"base_dir存在，内容: {os.listdir(base_dir)}")
        
        model_dir = os.path.join(base_dir, "separated", model_name)
        if os.path.exists(model_dir):
            print(f"model_dir存在，内容: {os.listdir(model_dir)}")
            
            audio_dir = os.path.join(model_dir, audio_name)
            if os.path.exists(audio_dir):
                print(f"audio_dir存在，内容: {os.listdir(audio_dir)}")
        
    # 使用glob查找所有可能的音频文件
    all_output_files = glob.glob(f"{base_dir}/**/*.mp3", recursive=True)
    print(f"找到的所有音频文件: {all_output_files}")
    
    # 从找到的文件中分类
    tracks = {
        "drums": None,
        "bass": None,
        "other": None,
        "vocals": None
    }
    
    for file_path in all_output_files:
        if "drums" in file_path:
            tracks["drums"] = file_path
        elif "bass" in file_path:
            tracks["bass"] = file_path
        elif "other" in file_path:
            tracks["other"] = file_path
        elif "vocals" in file_path:
            tracks["vocals"] = file_path
            
    print(f"找到的drums文件: {tracks['drums']}")
    print(f"找到的bass文件: {tracks['bass']}")
    print(f"找到的other文件: {tracks['other']}")
    print(f"找到的vocals文件: {tracks['vocals']}")
    
    # 检查是否找到了所有必需的文件
    if not all([tracks["drums"], tracks["bass"], tracks["other"]]):
        raise FileNotFoundError("未找到全部所需的音频轨道文件")
        
    return tracks


def create_accompaniment(tracks, output_path):
    """
    混合drums, bass和other轨道，生成伴奏
    
    参数:
        tracks: 包含各轨道路径的字典
        output_path: 输出伴奏文件路径
        
    返回:
        伴奏文件路径
    """
    print(f"伴奏混合文件路径: {output_path}")
    # 使用ffmpeg混合drums, bass和other轨道，生成伴奏
    accompaniment_cmd = [
        "ffmpeg", "-y",
        "-i", tracks["drums"],
        "-i", tracks["bass"],
        "-i", tracks["other"],
        "-filter_complex", "amix=inputs=3:duration=longest:dropout_transition=2",
        "-b:a", "320k",
        output_path
    ]
    subprocess.run(accompaniment_cmd, check=True)
    
    return output_path


def mix_audio(accompaniment_path, speaking_audio, output_path):
    """
    混合背景音乐和人声
    
    参数:
        accompaniment_path: 伴奏文件路径
        speaking_audio: 人声文件路径
        output_path: 输出混合音频文件路径
        
    返回:
        混合后的音频文件路径
    """
    print(f"混合后的音频文件路径: {output_path}")
    
    # 使用ffmpeg混合背景音乐和人声
    mix_cmd = [
        "ffmpeg", "-y",
        "-i", accompaniment_path,
        "-i", speaking_audio,
        "-filter_complex", "amix=inputs=2:duration=longest:dropout_transition=2:weights=1 1",
        "-b:a", "320k",
        output_path
    ]
    subprocess.run(mix_cmd, check=True)
    
    return output_path


def replace_video_audio(video_path, audio_path, output_path, subtitle_path=None):
    """
    将混合后的音频替换到原始视频中，可选择添加字幕
    
    参数:
        video_path: 视频文件路径
        audio_path: 音频文件路径
        output_path: 输出视频文件路径
        subtitle_path: 字幕文件路径（可选，仅支持SRT格式）
        
    返回:
        输出视频文件路径
    """
    print(f"将混合后的音频替换到原始视频中: {video_path}")
    
    output_cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
    ]
    
    # 如果提供了字幕文件，添加字幕输入
    if subtitle_path and os.path.exists(subtitle_path) and subtitle_path.lower().endswith('.srt'):
        output_cmd.extend(["-i", subtitle_path])
    
    # 基本输出选项
    output_cmd.extend([
        "-c:v", "copy",       # 保持视频质量
        "-c:a", "aac",        # 使用AAC编码音频
        "-b:a", "320k",       # 高音频比特率
        "-map", "0:v:0",      # 使用第一个输入的视频流
        "-map", "1:a:0",      # 使用第二个输入的音频流
    ])
    
    # 如果有字幕，添加字幕映射和相关选项
    if subtitle_path and os.path.exists(subtitle_path) and subtitle_path.lower().endswith('.srt'):
        output_cmd.extend([
            "-map", "2",      # 使用第三个输入的字幕流
            "-c:s", "mov_text"  # 使用mov_text编码字幕
        ])
    
    # 添加最终输出选项
    output_cmd.extend([
        "-shortest",          # 以最短的流长度为准
        output_path
    ])
    
    subprocess.run(output_cmd, check=True)
    
    print(f"成功生成文件: {output_path}")
    return output_path


def merge_audio(original_video, original_audio, speaking_audio, output_filename, subtitle_path=None):
    """
    将原始音频中分离出的背景音乐与新的人声音频合并，然后替换视频中的音频
    
    参数:
        original_video: 原始视频文件路径
        original_audio: 原始音频文件路径
        speaking_audio: 新的人声音频文件路径
        output_filename: 输出视频文件路径
        subtitle_path: 字幕文件路径（可选，仅支持SRT格式）
    """
    # 创建临时目录
    temp_dir = create_temp_directory()
    try:
        # 使用demucs分离音频
        demucs_output_dir = os.path.join(temp_dir, "demucs_output")
        separate_audio(original_audio, demucs_output_dir)
        
        # 获取分离出的音频轨道
        audio_name = Path(original_audio).stem
        tracks = find_audio_tracks(demucs_output_dir, audio_name)
        
        # 创建临时的伴奏混合文件
        accompaniment_path = os.path.join(temp_dir, "accompaniment.wav")
        create_accompaniment(tracks, accompaniment_path)
        
        # 创建临时混合的音频文件
        mixed_audio_path = os.path.join(temp_dir, "mixed_audio.wav")
        mix_audio(accompaniment_path, speaking_audio, mixed_audio_path)
        
        # 将混合后的音频替换到原始视频中，并可选择添加字幕
        return replace_video_audio(original_video, mixed_audio_path, output_filename, subtitle_path)
        
    finally:
        # 清理临时文件
        cleanup_temp_files(temp_dir)


if __name__ == "__main__":
        merge_audio(original_video="resources/videos/A_5Nd3vAG9k.mp4", 
                    original_audio="resources/audios/A_5Nd3vAG9k.mp3", 
                    speaking_audio="resources/audios/A_5Nd3vAG9k/A_5Nd3vAG9k.mp3", 
                    output_filename="resources/videos/merged_A_5Nd3vAG9k.mp4",
                    subtitle_path="resources/transcripts/merger_A_5Nd3vAG9k_cn.srt")  # 可以提供SRT字幕文件路径