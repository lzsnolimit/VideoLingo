#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

from merge_audio import merge_audio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio_to_subtitle import assembly_audio_to_subtitle
from download_youtube import download_youtube
from subtitle_to_speech import process_subtitles
from translate_subtitles import translate_srt_file


def main():
    url = "https://youtube.com/watch?v=A_5Nd3vAG9k"
    video_name = url.split("=")[1]
    
    #第一步：下载视频和音频
    # 使用默认参数下载视频（默认类型为video，质量为best）
    audio_result = download_youtube(url, content_type="audio", audio_format="mp3", audio_quality="0")
    video_result = download_youtube(url, content_type="video", quality="best")

    if video_result.startswith("下载失败") or video_result.startswith("发生错误"):
        print(f"错误: {video_result}")
        return 1
    
    if audio_result.startswith("下载失败") or audio_result.startswith("发生错误"):
        print(f"错误: {audio_result}")
        return 1
    
    print(f"下载成功，文件保存在: {video_result}")
    print(f"下载成功，文件保存在: {audio_result}")
    
    #第二步：将音频转换为字幕
    # 使用assembly_audio_to_subtitle函数处理音频文件
    subtitle_result = assembly_audio_to_subtitle(audio_result)
    
    if subtitle_result.startswith("错误"):
        print(f"错误: {subtitle_result}")
        return 1
    
    print(f"字幕文件已保存至: {subtitle_result}")

    #第三步：将字幕转换为汉语字幕
    # 获取输出文件名
    subtitle_name = os.path.basename(subtitle_result)
    name, ext = os.path.splitext(subtitle_name)
    chinese_subtitle = os.path.join(os.path.dirname(subtitle_result), f"{name}_cn{ext}")
    
    # 调用translate_srt_file函数将英文字幕翻译为中文字幕
    translated_subtitle = translate_srt_file(subtitle_result, chinese_subtitle)
    
    if not os.path.exists(translated_subtitle):
        print(f"错误: 翻译字幕失败")
        return 1
    
    print(f"中文字幕文件已保存至: {translated_subtitle}")
    
    #第四步：将汉语字幕转换为语音
    # 使用process_subtitles函数处理字幕文件
    generated_audio = process_subtitles(translated_subtitle, video_name, output_dir=f"resources/audios/{video_name}")
    return generated_audio

if __name__ == "__main__":
    # 完整流程测试
    # print(main())
    merge_audio(original_video="resources/videos/merger_A_5Nd3vAG9k.mp4", original_audio="resources/audios/A_5Nd3vAG9k.mp3", speaking_audio="resources/audios/A_5Nd3vAG9k/A_5Nd3vAG9k.mp3", output_filename="resources/results/A_5Nd3vAG9k.mp4")