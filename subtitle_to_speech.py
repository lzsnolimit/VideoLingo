import re
import os
import logging
from fish_audio_sdk import Prosody, ReferenceAudio, Session, TTSRequest
from pydub import AudioSegment
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("subtitle_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API密钥
api_key = "ed0df68c39384dcfa1c2c9be7b90e8f2"

def parse_subtitle(subtitle_file):
    """
    解析字幕文件，提取时间戳和文本
    返回格式: [(start_time, end_time, text), ...]
    时间单位: 毫秒
    """
    logger.info(f"开始解析字幕文件: {subtitle_file}")
    start_time = time.time()
    
    segments = []
    
    try:
        with open(subtitle_file, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.info(f"成功读取字幕文件，大小: {len(content)} 字节")
    except Exception as e:
        logger.error(f"读取字幕文件失败: {e}")
        raise
    
    # 匹配标准SRT格式: 数字序号 + 时间戳 + 文本
    pattern = r'(?:\d+\s*)?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\d+\s*\n|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    logger.info(f"找到 {len(matches)} 个字幕片段")
    
    for i, (start_time_str, end_time_str, text) in enumerate(matches):
        try:
            # 转换时间格式为毫秒
            start_time_ms = time_to_ms(start_time_str)
            end_time_ms = time_to_ms(end_time_str)
            # 清理文本（移除多余的空白和引号）
            cleaned_text = text.strip()
            
            # 记录每10个字幕的信息，避免日志过多
            if i % 10 == 0 or i == len(matches) - 1:
                logger.debug(f"解析第 {i+1}/{len(matches)} 个字幕: {start_time_str} --> {end_time_str}")
            
            segments.append((start_time_ms, end_time_ms, cleaned_text))
        except Exception as e:
            logger.error(f"解析字幕段落失败 [{start_time_str} --> {end_time_str}]: {e}")
    
    # 按照开始时间排序字幕
    segments.sort(key=lambda x: x[0])
    
    end_time = time.time()
    logger.info(f"字幕解析完成，耗时: {end_time - start_time:.2f} 秒")
    return segments

def time_to_ms(time_str):
    """将时间字符串 (HH:MM:SS.mmm) 转换为毫秒"""
    try:
        # 替换逗号为点，以便于处理
        time_str = time_str.replace(',', '.')
        h, m, s = time_str.split(':')
        return int(h) * 3600000 + int(m) * 60000 + int(float(s) * 1000)
    except Exception as e:
        logger.error(f"时间格式转换失败 [{time_str}]: {e}")
        raise

def text_to_speech(
    text,
    api_key,
    reference_audio_path,
    output_path,
    reference_text
):
    """
    将文本转换为语音
    返回生成的语音文件路径
    """
    logger.info(f"开始文本转语音: {output_path}")
    start_time = time.time()
    
    try:
        if not text.strip():
            # 如果文本为空，创建一个空白音频文件
            logger.info(f"文本为空，创建空白音频")
            silent = AudioSegment.silent(duration=100, frame_rate=48000)  # 100毫秒的空白
            silent.export(output_path, format="mp3", bitrate="320k")
            return output_path
        
        # 记录较长文本的前50个字符
        log_text = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"处理文本: {log_text}")
        
        session = Session(api_key)
        
        # 准备TTS请求
        request = TTSRequest(
            prosody=Prosody(speed=1.0),  # 控制音频速度
            text=text,
            references=[
                ReferenceAudio(
                    audio=open(reference_audio_path, "rb").read(),
                    text=reference_text
                )
            ]
        )
        
        # 生成语音并保存到文件
        logger.info(f"发送TTS请求并保存到: {output_path}")
        with open(output_path, "wb") as f:
            for chunk in session.tts(request):
                f.write(chunk)
        
        end_time = time.time()
        logger.info(f"TTS完成，耗时: {end_time - start_time:.2f} 秒")
        return output_path
    except Exception as e:
        logger.error(f"文本转语音失败: {e}")
        # 出错时创建一个空白文件，确保流程可以继续
        try:
            silent = AudioSegment.silent(duration=1000, frame_rate=48000)
            silent.export(output_path, format="mp3", bitrate="320k")
            logger.warning("创建了替代的空白音频文件")
        except:
            logger.error("无法创建替代音频文件")
        return output_path

def get_audio_duration(audio_file):
    """获取音频文件的持续时间（毫秒）"""
    try:
        audio = AudioSegment.from_file(audio_file)
        duration = len(audio)
        logger.debug(f"音频文件 {audio_file} 长度: {duration}ms")
        return duration
    except Exception as e:
        logger.error(f"获取音频时长失败 [{audio_file}]: {e}")
        return 0  # 出错时返回0长度

def count_chinese_chars(text):
    """计算文本中汉字的数量"""
    count = 0
    for char in text:
        if '\u4e00' <= char <= '\u9fff':  # Unicode范围内的汉字
            count += 1
    return count

def ensure_audio_quality(audio_segment, target_frame_rate=48000):
    """确保音频段落使用一致的高质量参数"""
    # 如果当前采样率与目标不同，进行转换
    if audio_segment.frame_rate != target_frame_rate:
        audio_segment = audio_segment.set_frame_rate(target_frame_rate)
    # 确保音频为立体声
    if audio_segment.channels == 1:
        audio_segment = audio_segment.set_channels(2)
    return audio_segment

def create_silence(duration, output_path=None):
    """创建指定时长的空白音频"""
    # 确保不创建负时长的空白
    duration = max(0, duration)
    # 使用更高的采样率创建空白音频
    silence = AudioSegment.silent(duration=duration, frame_rate=48000)
    if output_path:
        silence.export(output_path, format="mp3", bitrate="320k")
    return silence

def process_subtitles(subtitle_file, file_name, output_dir="resources/audios"):
    """
    处理字幕文件，生成对应的语音文件
    1. 解析字幕
    2. 为每个字幕段落生成语音
    3. 根据字幕时长添加空白并合并所有语音段落
    """
    logger.info("="*80)
    logger.info(f"开始处理字幕转语音任务")
    logger.info(f"字幕文件: {subtitle_file}")
    logger.info(f"输出目录: {output_dir}")
    start_time_total = time.time()
    
    # 创建输出目录
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"输出目录已准备: {output_dir}")
    except Exception as e:
        logger.error(f"创建输出目录失败: {e}")
        raise
    
    # 解析字幕
    segments = parse_subtitle(subtitle_file)
    logger.info(f"共有 {len(segments)} 个字幕段落需要处理")
    
    # 第一步：生成所有TTS音频，不添加空白
    logger.info("="*50)
    logger.info("第一步：生成所有TTS音频")
    
    segment_audio_files = []
    successful_segments = 0
    
    for i, (start_time, end_time, text) in enumerate(segments):
        segment_duration = end_time - start_time
        logger.info(f"处理第 {i+1}/{len(segments)} 段字幕 [{(i+1)/len(segments)*100:.1f}%]:")
        logger.info(f"时间: {start_time}ms -> {end_time}ms (持续 {segment_duration}ms)")
        logger.info(f"文本: {text}")
        
        segment_start_time = time.time()
        
        # 生成语音文件路径
        audio_file = os.path.join(output_dir, f"segment_{i:04d}.mp3")
        
        # 检查文件是否已存在
        if os.path.exists(audio_file):
            logger.info(f"文件已存在，跳过TTS生成: {audio_file}")
            # 获取已存在文件的音频时长
            try:
                audio_duration = get_audio_duration(audio_file)
                logger.info(f"已存在音频长度: {audio_duration}ms, 字幕长度: {segment_duration}ms")
                
                # 计算每个汉字的平均毫秒数
                chinese_char_count = count_chinese_chars(text)
                if chinese_char_count > 0:
                    ms_per_char = audio_duration / chinese_char_count
                    logger.info(f"已存在音频统计: {chinese_char_count}个汉字, 平均每个汉字{ms_per_char:.2f}ms")
                
                segment_audio_files.append((i, audio_file, audio_duration, start_time, end_time))
                successful_segments += 1
                
                segment_end_time = time.time()
                logger.info(f"跳过TTS生成，耗时: {segment_end_time - segment_start_time:.2f} 秒")
                logger.info("-" * 50)
                continue
            except Exception as e:
                logger.error(f"获取已存在文件时长失败: {e}")
                # 如果获取失败，删除可能损坏的文件并重新生成
                try:
                    os.remove(audio_file)
                    logger.info(f"删除可能损坏的文件: {audio_file}")
                except:
                    logger.warning(f"无法删除可能损坏的文件: {audio_file}")
        
        try:
            # 生成语音文件
            text_to_speech(
                text=text,
                api_key=api_key,
                reference_audio_path="resources/audios/peiyin.mp3",
                output_path=audio_file,
                reference_text="这是久负盛名的核桃杯，如果你想要它，你首先需要赢得我在自家后院设置的大部分比赛活动，其次，成为一只松鼠。欢迎来到我在后院与松鼠进行艰苦战斗的第三年也是最后一年。然后爆米花，因为今年我们不仅有惊人的运动壮举和很多险胜，还有物种间的战斗、Fat Gus 婴儿时期的家庭视频，以及震撼整个社区的丑闻，你不得不去看，相信它。所以，抓紧你的核桃，让我们开始吧。体育迷们，您好，欢迎来到 Backyard 夏季运动会，世界上最伟大的浓密尾巴运动员将参加七个不同的项目，包括跳远、跳高和旋转平衡木，所有这些都是为了荣耀和享有盛誉的核桃杯。我是 Chuck Acorns。我是 Jimmy。就跟 Jimmy 一起去？是的，就是 Jimmy。好的，欢迎。"
                #reference_text="Through a sunlit forest, a curious fox with a fluffy tail and bright, glimmering eyes darted between the trees, its tiny paws leaving soft imprints on the mossy ground. Pausing to sniff a patch of wildflowers, it tilted its head, listening to the distant chirp of a bird, as if the entire forest were a melody it alone could understand."
                # reference_text="当苏联将坦克与南极洲的冰原相结合，会发生什么？你将得到可能是人类史上最疯狂的陆地载具。它能在零下57摄氏度（-70华氏度）的环境中工作，穿越暴风雪运输大宗货物，同时为乘员提供舒适的居住空间。与早期美国征服南极的尝试不同，俄罗斯人实际研发了多个迭代版本，其最新型号甚至在本世纪仍在服役。这就是苏联南极坦克的故事——在美国人失败的地方，他们成功了。来自哈尔科夫的传奇——哈尔科夫尚卡。"
            )
            
            # 获取生成的语音长度
            audio_duration = get_audio_duration(audio_file)
            logger.info(f"语音长度: {audio_duration}ms, 字幕长度: {segment_duration}ms")
            
            # 计算每个汉字的平均毫秒数
            chinese_char_count = count_chinese_chars(text)
            if chinese_char_count > 0:
                ms_per_char = audio_duration / chinese_char_count
                logger.info(f"TTS音频统计: {chinese_char_count}个汉字, 平均每个汉字{ms_per_char:.2f}ms")
            
            segment_audio_files.append((i, audio_file, audio_duration, start_time, end_time))
            successful_segments += 1
            
            segment_end_time = time.time()
            logger.info(f"段落处理完成，耗时: {segment_end_time - segment_start_time:.2f} 秒")
            logger.info("-" * 50)
            
        except Exception as e:
            logger.error(f"处理段落 {i+1} 失败: {e}")
            # 创建空白音频作为替代
            try:
                audio_file = os.path.join(output_dir, f"segment_{i:04d}_empty.mp3")
                silent = AudioSegment.silent(duration=100, frame_rate=48000)
                silent.export(audio_file, format="mp3", bitrate="320k")
                segment_audio_files.append((i, audio_file, 100, start_time, end_time))
                logger.warning(f"为失败的段落创建了空白音频替代")
            except:
                logger.error("创建替代空白音频也失败了")
    
    # 第二步：根据字幕时长添加空白并合并
    logger.info("="*50)
    logger.info("第二步：根据字幕时长添加空白并合并")
    
    all_audio_segments = []
    current_time = 0
    accumulated_overrun = 0
    
    # 检查第一个字幕是否从0时间开始，如果不是，添加空白音频
    if segments and segments[0][0] > 0:
        first_subtitle_start_time = segments[0][0]
        logger.info(f"第一个字幕不是从0时间开始的，开始时间为: {first_subtitle_start_time}ms")
        logger.info(f"添加 {first_subtitle_start_time}ms 的空白音频到开头")
        
        # 创建空白音频并保存
        initial_silence_file = os.path.join(output_dir, "initial_silence.mp3")
        silence = create_silence(first_subtitle_start_time, initial_silence_file)
        
        # 添加到音频列表
        all_audio_segments.append(silence)
        logger.info(f"已添加初始空白音频: {first_subtitle_start_time}ms")
        current_time = first_subtitle_start_time
    
    # 按照索引排序音频文件
    segment_audio_files.sort(key=lambda x: x[0])
    
    # 处理每个音频段落和可能的间隙
    for i, (segment_idx, audio_file, audio_duration, start_time, end_time) in enumerate(segment_audio_files):
        segment_duration = end_time - start_time
        
        # 检查当前字幕与上一个字幕之间是否有间隙
        if start_time > current_time:
            gap_duration = start_time - current_time
            logger.info(f"检测到字幕间隙: {current_time}ms -> {start_time}ms (持续 {gap_duration}ms)")
            
            # 如果有累积的超时，尝试从间隙中减去
            if accumulated_overrun > 0:
                deduction = min(accumulated_overrun, gap_duration)
                gap_duration -= deduction
                accumulated_overrun -= deduction
                logger.info(f"从间隙中减去 {deduction}ms 的累积超时，剩余间隙: {gap_duration}ms, 剩余累积超时: {accumulated_overrun}ms")
            
            if gap_duration > 0:
                # 创建并添加间隙音频
                gap_silence_file = os.path.join(output_dir, f"gap_silence_{i:04d}.mp3")
                gap_silence = create_silence(gap_duration, gap_silence_file)
                all_audio_segments.append(gap_silence)
                logger.info(f"已添加间隙空白音频: {gap_duration}ms")
        
        # 加载当前音频段落 - 保持原始TTS文件不变
        try:
            # 加载原始TTS音频
            original_audio = AudioSegment.from_file(audio_file)
            # 应用音频质量控制
            original_audio = ensure_audio_quality(original_audio)
            
            # 检查语音是否超出字幕时长
            if audio_duration > segment_duration:
                # 语音比字幕长，记录超出时间
                overrun = audio_duration - segment_duration
                accumulated_overrun += overrun
                logger.warning(f"语音长度超出字幕时间 {overrun}ms, 累计超时: {accumulated_overrun}ms")
                
                # 直接添加原始音频，不做修改
                all_audio_segments.append(original_audio)
            elif audio_duration < segment_duration:
                # 语音比字幕短，考虑是否有累积的超时可以抵消
                silence_duration = segment_duration - audio_duration
                
                # 如果有累积的超时，尝试减少需要添加的空白
                if accumulated_overrun > 0:
                    deduction = min(accumulated_overrun, silence_duration)
                    silence_duration -= deduction
                    accumulated_overrun -= deduction
                    logger.info(f"从需要添加的空白中减去 {deduction}ms 的累积超时，剩余需添加空白: {silence_duration}ms, 剩余累积超时: {accumulated_overrun}ms")
                
                # 添加需要的空白（可能已被减少）
                if silence_duration > 0:
                    logger.info(f"添加 {silence_duration}ms 空白")
                    # 创建一个新的音频对象（原始音频+空白），而不是修改原始音频
                    silence = AudioSegment.silent(duration=silence_duration, frame_rate=48000)
                    combined_audio = original_audio + silence
                    all_audio_segments.append(combined_audio)
                else:
                    # 不需要添加空白，直接使用原始音频
                    all_audio_segments.append(original_audio)
            else:
                # 音频长度正好等于字幕长度，直接使用原始音频
                all_audio_segments.append(original_audio)
            
            # 更新当前时间点到字幕结束时间，而非实际音频结束时间
            # 这样可以更好地维持整体时间轴
            current_time = end_time
            
            # 每处理5个片段保存一次，避免内存过大
            if (i+1) % 5 == 0 or i == len(segment_audio_files) - 1:
                logger.info(f"合并临时片段 (共 {len(all_audio_segments)} 个)")
                temp_combined = sum(all_audio_segments)
                # 应用音频质量控制
                temp_combined = ensure_audio_quality(temp_combined)
                temp_output = os.path.join(output_dir, f"combined_temp_{i//5}.mp3")
                logger.info(f"保存临时文件: {temp_output}")
                temp_combined.export(temp_output, format="mp3", bitrate="320k")
                all_audio_segments = [AudioSegment.from_file(temp_output)]
                
        except Exception as e:
            logger.error(f"处理音频段落 {segment_idx+1} 失败: {e}")
            # 添加空白音频以保持时间轴同步
            try:
                silence_duration = segment_duration
                # 如果有累积的超时，也尝试减少空白
                if accumulated_overrun > 0:
                    deduction = min(accumulated_overrun, silence_duration)
                    silence_duration -= deduction
                    accumulated_overrun -= deduction
                    logger.info(f"从错误替代空白中减去 {deduction}ms 的累积超时，剩余空白: {silence_duration}ms, 剩余累积超时: {accumulated_overrun}ms")
                
                silence = AudioSegment.silent(duration=silence_duration, frame_rate=48000)
                all_audio_segments.append(silence)
                logger.warning(f"添加 {silence_duration}ms 空白代替失败的音频段落")
                # 更新当前时间点
                current_time = end_time
            except:
                logger.error("添加替代空白音频也失败了")
    
    # 最终报告累积超时情况
    if accumulated_overrun > 0:
        logger.warning(f"最终仍有 {accumulated_overrun}ms 的累积超时未能抵消")
    
    # 合并所有音频
    logger.info("开始最终合并")
    try:
        final_audio = sum(all_audio_segments)
        # 应用最终音频质量控制
        final_audio = ensure_audio_quality(final_audio)
        
        # 输出最终文件
        final_output = os.path.join(output_dir, "final_output.mp3")
        logger.info(f"导出最终文件: {final_output}")
        final_audio.export(final_output, format="mp3", bitrate="320k")
        
        total_duration = len(final_audio) / 1000  # 秒
        end_time_total = time.time()
        total_process_time = end_time_total - start_time_total
        
        # 计算所有段落中汉字总数和平均时长
        total_chinese_chars = 0
        for _, _, text in segments:
            total_chinese_chars += count_chinese_chars(text)
        
        if total_chinese_chars > 0:
            avg_ms_per_char = (total_duration * 1000) / total_chinese_chars
            logger.info(f"整体音频统计: 总计{total_chinese_chars}个汉字, 平均每个汉字{avg_ms_per_char:.2f}ms")
        
        logger.info("="*80)
        logger.info(f"处理完成! 总耗时: {total_process_time:.2f} 秒")
        logger.info(f"最终音频文件: {final_output}")
        logger.info(f"音频长度: {total_duration:.2f} 秒")
        logger.info(f"成功处理 {successful_segments}/{len(segments)} 个段落 ({successful_segments/len(segments)*100:.1f}%)")
        
        # 计算最后一个字幕的结束时间
        if segments:
            last_subtitle_end = segments[-1][1]
            subtitle_total_duration = last_subtitle_end / 1000  # 秒
            logger.info(f"字幕总时长: {subtitle_total_duration:.2f} 秒")
            logger.info(f"音频时长与字幕时长差异: {total_duration - subtitle_total_duration:.2f} 秒")
        
        logger.info("="*80)
        
        return final_output
    except Exception as e:
        logger.error(f"最终合并失败: {e}")
        logger.error("处理未完成")
        return None


if __name__ == "__main__":
    process_subtitles("resources/transcripts/merger_DTvS9lvRxZ8_cn.srt", "DTvS9lvRxZ8", output_dir="resources/audios/DTvS9lvRxZ8")