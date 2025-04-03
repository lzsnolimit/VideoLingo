import re
import os
from typing import List, Tuple, Dict
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser


def translate_srt_file(input_path: str, output_path: str, log_file=None, target_language:str="中文", max_retry:int=5) -> str:
    """
    将SRT字幕文件翻译成目标语言
    
    Args:
        input_path: 输入SRT文件路径
        output_path: 输出SRT文件路径
        log_file: 日志文件路径，如果不为None则会记录翻译日志
        target_language: 目标语言，默认为中文
        max_retry: 翻译失败时的最大重试次数，默认为5
        
    Returns:
        输出文件路径，如果所有重试都失败则返回空字符串
    """
    print(f"开始翻译字幕文件: {input_path} -> {output_path}")
    print(f"目标语言: {target_language}")
    
    # 读取SRT文件
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析SRT文件
    subtitle_blocks = parse_srt(content)
    print(f"共解析出 {len(subtitle_blocks)} 个字幕块")
    
    # 收集所有文本，添加ID标识符
    text_with_ids = []
    for i, (idx, timestamp, text) in enumerate(subtitle_blocks):
        # 使用唯一标识符标记每个字幕块
        block_id = f"[BLOCK_{i+1}]"
        text_with_ids.append(f"{block_id}\n{text}")
    
    # 将所有文本合并成一个大文本
    combined_text = "\n\n".join(text_with_ids)
    
    # 设置翻译提示模板
    template = """
    你是一位精通{target_language}的专业字幕翻译，尤其擅长将口语化的内容翻译成准确、自然的字幕。

    规则：
    - 准确传达原文的事实、背景和情感
    - 保留专业术语、品牌名称和人名
    - 使译文符合{target_language}的表达习惯
    - 保持字幕简洁，适合观众快速阅读
    - 每个字幕块都有一个唯一标识符，如[BLOCK_1]，[BLOCK_2]等，翻译时必须保留这些标识符
    - 保持原文的段落数量和顺序
    - 只返回翻译结果，不要包含任何解释或原文

    请将以下英文字幕翻译成{target_language}：

    {text}
    
    翻译结果：
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # 初始化LangChain模型和链
    print("初始化翻译模型...")
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.6,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        # other params...
    )
    
    # 使用RunnableSequence代替LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # 添加重试逻辑
    retry_count = 0
    successful_translation = False
    
    while retry_count < max_retry and not successful_translation:
        try:
            # 一次性翻译所有字幕
            print(f"开始翻译尝试 {retry_count + 1}/{max_retry}...")
            translated_combined_text = chain.invoke({"text": combined_text, "target_language": target_language})
            
            # 解析翻译结果，按ID提取
            translated_blocks_map = extract_translations_by_id(translated_combined_text)
            
            # 检查是否所有块都有对应的翻译
            if len(translated_blocks_map) == len(subtitle_blocks):
                successful_translation = True
                print(f"翻译成功！")
            else:
                print(f"警告：翻译后的字幕块数量 ({len(translated_blocks_map)}) 与原始字幕块数量 ({len(subtitle_blocks)}) 不一致！")
                missing_blocks = [i+1 for i in range(len(subtitle_blocks)) if f"BLOCK_{i+1}" not in translated_blocks_map]
                if missing_blocks:
                    print(f"缺失的块: {missing_blocks}")
                retry_count += 1
        except Exception as e:
            print(f"翻译过程中出现错误: {str(e)}")
            retry_count += 1
            
    # 如果所有重试都失败，尝试逐块翻译
    if not successful_translation:
        print(f"所有批量翻译尝试均失败，切换到逐块翻译模式...")
        try:
            return translate_srt_file_by_block(input_path, output_path, log_file, target_language, max_retry)
        except Exception as e:
            print(f"逐块翻译也失败了。错误: {str(e)}")
            print("所有翻译方法均失败，返回空字符串。")
            return ""
    
    # 记录日志
    if log_file:
        with open(log_file, 'w', encoding='utf-8') as f:
            for i, (idx, timestamp, original_text) in enumerate(subtitle_blocks):
                block_id = f"BLOCK_{i+1}"
                translated_text = translated_blocks_map.get(block_id, "翻译缺失")
                f.write(f"字幕块 {i+1} (ID: {idx}):\n原文: {original_text}\n翻译: {translated_text}\n\n")
    
    # 组合翻译后的字幕块
    translated_blocks = []
    for i, (idx, timestamp, original_text) in enumerate(subtitle_blocks):
        block_id = f"BLOCK_{i+1}"
        translated_text = translated_blocks_map.get(block_id, original_text)  # 如果没有翻译，使用原文
        translated_blocks.append((idx, timestamp, translated_text))
    
    # 将翻译后的字幕块重新组合成SRT格式
    translated_content = format_srt(translated_blocks)
    
    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    print(f"翻译完成！已保存到: {output_path}")
    if log_file:
        print(f"翻译日志已保存到: {log_file}")
    
    return output_path


def extract_translations_by_id(translated_text: str) -> Dict[str, str]:
    """
    从翻译文本中提取各个带ID的字幕块
    
    Args:
        translated_text: 翻译后的带ID文本
        
    Returns:
        字典，键为块ID，值为翻译后的文本
    """
    # 用正则表达式匹配 [BLOCK_数字] 开头的文本块
    pattern = r'\[BLOCK_(\d+)\]\s*\n([\s\S]*?)(?=\n\s*\[BLOCK_\d+\]|\s*$)'
    matches = re.findall(pattern, translated_text)
    
    result = {}
    for block_num, text in matches:
        block_id = f"BLOCK_{block_num}"
        result[block_id] = text.strip()
    
    return result


def translate_srt_file_by_block(input_path: str, output_path: str, log_file=None, target_language:str="中文", max_retry:int=5) -> str:
    """
    逐块翻译SRT字幕文件（备用方法）
    
    Args:
        input_path: 输入SRT文件路径
        output_path: 输出SRT文件路径
        log_file: 日志文件路径，如果不为None则会记录翻译日志
        target_language: 目标语言，默认为中文
        max_retry: 翻译失败时的最大重试次数，默认为5
        
    Returns:
        输出文件路径，如果所有重试都失败则返回空字符串
    """
    print("切换到逐块翻译模式...")
    
    # 读取SRT文件
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析SRT文件
    subtitle_blocks = parse_srt(content)
    
    # 设置翻译提示模板
    template = """
    你是一位精通{target_language}的专业字幕翻译，尤其擅长将口语化的内容翻译成准确、自然的字幕。

    规则：
    - 准确传达原文的事实、背景和情感
    - 保留专业术语、品牌名称和人名
    - 使译文符合{target_language}的表达习惯
    - 保持字幕简洁，适合观众快速阅读
    - 只返回翻译结果，不要包含任何解释或原文

    请将以下英文字幕翻译成{target_language}：

    {text}
    
    翻译结果：
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # 初始化LangChain模型和链
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.6,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        # other params...
    )
    
    # 使用RunnableSequence代替LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # 翻译每个字幕块
    translated_blocks = []
    
    if log_file:
        log_mode = 'a' if os.path.exists(log_file) else 'w'
        with open(log_file, log_mode, encoding='utf-8') as f:
            f.write("=== 逐块翻译模式 ===\n\n")
    
    # 跟踪失败的翻译块
    failed_blocks = 0
    
    for i, (idx, timestamp, text) in enumerate(subtitle_blocks):
        print(f"正在翻译第 {i+1}/{len(subtitle_blocks)} 个字幕块 (ID: {idx})...")
        
        # 添加重试逻辑
        block_retry_count = 0
        block_successful = False
        translated_text = text  # 默认使用原文
        
        while block_retry_count < max_retry and not block_successful:
            try:
                # 调用模型进行翻译
                print(f"块 {i+1} 的翻译尝试 {block_retry_count + 1}/{max_retry}...")
                translated_text = chain.invoke({"text": text, "target_language": target_language})
                translated_text = translated_text.strip()
                
                # 检查翻译是否有效（至少不为空）
                if translated_text:
                    block_successful = True
                else:
                    print(f"块 {i+1} 的翻译为空，重试...")
                    block_retry_count += 1
            except Exception as e:
                print(f"块 {i+1} 翻译出错: {str(e)}，重试...")
                block_retry_count += 1
        
        # 如果所有重试都失败
        if not block_successful:
            print(f"块 {i+1} 的所有翻译尝试都失败！")
            failed_blocks += 1
        
        # 记录日志
        if log_file:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"字幕块 {i+1} (ID: {idx}):\n原文: {text}\n翻译: {translated_text}\n\n")
        
        # 将翻译后的字幕块添加到结果列表
        translated_blocks.append((idx, timestamp, translated_text))
    
    # 检查是否翻译大部分失败
    if failed_blocks > len(subtitle_blocks) * 0.5:  # 如果超过一半的块翻译失败
        print(f"警告：超过一半的字幕块翻译失败 ({failed_blocks}/{len(subtitle_blocks)})！")
        print("翻译质量可能不可接受，放弃翻译。")
        return ""
    
    # 将翻译后的字幕块重新组合成SRT格式
    translated_content = format_srt(translated_blocks)
    
    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    print(f"逐块翻译完成！已保存到: {output_path}")
    print(f"成功翻译: {len(subtitle_blocks) - failed_blocks}/{len(subtitle_blocks)} 个字幕块")
    if log_file:
        print(f"翻译日志已保存到: {log_file}")
    
    return output_path


def parse_srt(content: str) -> List[Tuple[str, str, str]]:
    """
    解析SRT文件内容
    
    Args:
        content: SRT文件内容
        
    Returns:
        解析后的字幕块列表，每个元素为(序号, 时间戳, 文本)的元组
    """
    # 使用正则表达式匹配SRT文件的各个部分
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n((?:.+\n)+?)(?:\n|$)'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    subtitle_blocks = []
    for match in matches:
        idx = match[0]
        timestamp = match[1]
        text = match[2].strip()
        subtitle_blocks.append((idx, timestamp, text))
    
    return subtitle_blocks


def format_srt(blocks: List[Tuple[str, str, str]]) -> str:
    """
    将字幕块列表格式化为SRT格式的字符串
    
    Args:
        blocks: 字幕块列表，每个元素为(序号, 时间戳, 文本)的元组
        
    Returns:
        SRT格式的字符串
    """
    formatted_content = ""
    for idx, timestamp, text in blocks:
        formatted_content += f"{idx}\n{timestamp}\n{text}\n\n"
    
    return formatted_content.strip()


if __name__ == "__main__":
    translate_srt_file("resources/transcripts/merger_hFZFjoX2cGg.srt", "output.srt", log_file="translation_log.txt", max_retry=5)