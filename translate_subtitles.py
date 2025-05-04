import re
import os
from typing import List, Tuple, Dict
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain_core.output_parsers import StrOutputParser


def translate_srt_file(input_path: str, output_path: str, log_file=None, target_language:str="Chinese", max_retry:int=5) -> str:
    """
    Translate SRT subtitle file to target language
    
    Args:
        input_path: Input SRT file path
        output_path: Output SRT file path
        log_file: Log file path, if not None will record translation logs
        target_language: Target language, default is Chinese
        max_retry: Maximum number of retry attempts if translation fails, default is 5
        
    Returns:
        Output file path, or empty string if all retries fail
    """
    print(f"Starting subtitle translation: {input_path} -> {output_path}")
    print(f"Target language: {target_language}")
    
    # Read SRT file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse SRT file
    subtitle_blocks = parse_srt(content)
    print(f"Parsed {len(subtitle_blocks)} subtitle blocks")
    
    # Collect all text with ID identifiers
    text_with_ids = []
    for i, (idx, timestamp, text) in enumerate(subtitle_blocks):
        # Mark each subtitle block with unique identifier
        block_id = f"[BLOCK_{i+1}]"
        text_with_ids.append(f"{block_id}\n{text}")
    
    # Split subtitles into batches of 30, with 10 before and after as context
    batch_size = 20
    context_size = 10
    total_blocks = len(text_with_ids)
    
    # Prepare dictionary to store all batch translation results
    all_translated_blocks_map = {}
    
    # Set up translation prompt template
    template = """
    You are a professional subtitle translator fluent in {target_language}, especially skilled at translating conversational content into accurate and natural subtitles.

    Rules:
    - Accurately convey facts, context, and emotions from the original text
    - Preserve technical terms, brand names, and person names
    - Make translations conform to {target_language} expression habits
    - Keep subtitles concise for quick reading by viewers
    - Each subtitle block has a unique identifier like [BLOCK_1], [BLOCK_2], etc., which must be preserved during translation
    - Only translate the parts marked as "Need to translate", the parts marked as "Context" are for reference only and should not be translated
    - Maintain the original number and order of paragraphs
    - Only return translation results, don't include any explanations or original text

    Below is the subtitle content, where the "Need to translate" part needs translation, and the "Context" part is provided for reference:

    {text}
    
    Translation result (only return translation results for the "Need to translate" part):
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # Initialize LangChain model and chain
    print("Initializing translation model...")
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.6,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        # other params...
    )
    
    # Use RunnableSequence instead of LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # Initialize translation status tracking
    failed_batches = []
    
    # Translate in batches
    for batch_start in range(0, total_blocks, batch_size):
        batch_end = min(batch_start + batch_size, total_blocks)
        context_start = max(0, batch_start - context_size)
        context_end = min(total_blocks, batch_end + context_size)
        
        # Build batch text with context
        batch_text = []
        
        # Add preceding context
        if context_start < batch_start:
            batch_text.append("【Context (for reference only, do not translate)】")
            for i in range(context_start, batch_start):
                batch_text.append(text_with_ids[i])
            batch_text.append("【End of context】\n")
        
        # Add main content to translate
        batch_text.append("【Need to translate】")
        for i in range(batch_start, batch_end):
            batch_text.append(text_with_ids[i])
        batch_text.append("【End of need to translate】\n")
        
        # Add following context
        if batch_end < context_end:
            batch_text.append("【Context (for reference only, do not translate)】")
            for i in range(batch_end, context_end):
                batch_text.append(text_with_ids[i])
            batch_text.append("【End of context】")
        
        # Combine batch text
        combined_batch_text = "\n\n".join(batch_text)
        
        print(f"Translating batch {batch_start//batch_size + 1}/{(total_blocks-1)//batch_size + 1} (subtitles {batch_start+1}-{batch_end})...")
        
        # Add retry logic
        retry_count = 0
        batch_successful = False
        
        while retry_count < max_retry and not batch_successful:
            try:
                print(f"Batch translation attempt {retry_count + 1}/{max_retry}...")
                translated_batch_text = chain.invoke({"text": combined_batch_text, "target_language": target_language})
                
                # Parse translation results by ID
                translated_blocks_map = extract_translations_by_id(translated_batch_text)
                
                # Check if all blocks that needed translation have corresponding translations
                expected_blocks = batch_end - batch_start
                actual_blocks = len(translated_blocks_map)
                
                if actual_blocks == expected_blocks:  # Don't allow any missing blocks
                    batch_successful = True
                    print(f"Batch translation successful! Translated {actual_blocks}/{expected_blocks} subtitle blocks")
                    
                    # Merge translation results to total results
                    all_translated_blocks_map.update(translated_blocks_map)
                else:
                    print(f"Warning: Missing subtitle blocks after translation, actual: {actual_blocks}, expected: {expected_blocks}")
                    missing_blocks = [f"BLOCK_{i+1}" for i in range(batch_start, batch_end) 
                                     if f"BLOCK_{i+1}" not in translated_blocks_map]
                    if missing_blocks:
                        print(f"Missing blocks: {', '.join(missing_blocks[:10])}{' etc...' if len(missing_blocks) > 10 else ''}")
                    retry_count += 1
            except Exception as e:
                print(f"Error during batch translation: {str(e)}")
                retry_count += 1
        
        # If all retries for this batch fail
        if not batch_successful:
            print(f"All translation attempts for batch {batch_start//batch_size + 1} failed!")
            failed_batches.append((batch_start, batch_end))
    
    # Process all failed batches, try translating block by block
    if failed_batches:
        print(f"There are {len(failed_batches)} failed batches, trying to translate these batches block by block...")
        
        for batch_start, batch_end in failed_batches:
            print(f"Translating failed batch block by block: {batch_start+1}-{batch_end}...")
            
            for i in range(batch_start, batch_end):
                block_id = f"BLOCK_{i+1}"
                if block_id not in all_translated_blocks_map:
                    try:
                        # Try translating this block separately
                        single_text = text_with_ids[i]
                        translated_single = translate_single_block(single_text, target_language, max_retry)
                        if translated_single:
                            # Extract ID and translated text
                            block_match = re.match(r'\[BLOCK_(\d+)\]\s*\n([\s\S]*)', translated_single)
                            if block_match:
                                block_num = block_match.group(1)
                                block_text = block_match.group(2).strip()
                                all_translated_blocks_map[f"BLOCK_{block_num}"] = block_text
                    except Exception as e:
                        print(f"Single block translation failed ({block_id}): {str(e)}")
    
    # Check overall translation completion
    total_expected = len(subtitle_blocks)
    total_translated = len(all_translated_blocks_map)
    
    if total_translated < total_expected:  # Don't allow any missing blocks
        print(f"Warning: Translation has missing blocks ({total_translated}/{total_expected})!")
        missing_blocks = [f"BLOCK_{i+1}" for i in range(len(subtitle_blocks)) 
                         if f"BLOCK_{i+1}" not in all_translated_blocks_map]
        if len(missing_blocks) <= 10:
            print(f"Missing blocks: {', '.join(missing_blocks)}")
        else:
            print(f"Number of missing blocks: {len(missing_blocks)}")
            
        print("Trying to use backup block-by-block translation method to fill in missing parts...")
        try:
            return translate_srt_file_by_block(input_path, output_path, log_file, target_language, max_retry)
        except Exception as e:
            print(f"Backup translation method also failed. Error: {str(e)}")
            print("All translation methods failed, returning empty string.")
            return ""
    
    # Record logs
    if log_file:
        with open(log_file, 'w', encoding='utf-8') as f:
            for i, (idx, timestamp, original_text) in enumerate(subtitle_blocks):
                block_id = f"BLOCK_{i+1}"
                translated_text = all_translated_blocks_map.get(block_id, "Translation missing")
                f.write(f"Subtitle block {i+1} (ID: {idx}):\nOriginal: {original_text}\nTranslation: {translated_text}\n\n")
    
    # Combine translated subtitle blocks
    translated_blocks = []
    for i, (idx, timestamp, original_text) in enumerate(subtitle_blocks):
        block_id = f"BLOCK_{i+1}"
        translated_text = all_translated_blocks_map.get(block_id, original_text)  # Use original text if no translation
        translated_blocks.append((idx, timestamp, translated_text))
    
    # Recombine translated subtitle blocks into SRT format
    translated_content = format_srt(translated_blocks)
    
    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    print(f"Translation complete! Saved to: {output_path}")
    print(f"Translation completion: {total_translated}/{total_expected} ({total_translated/total_expected*100:.1f}%)")
    if log_file:
        print(f"Translation log saved to: {log_file}")
    
    return output_path


def translate_single_block(block_text: str, target_language: str, max_retry: int=3) -> str:
    """
    Translate a single subtitle block
    
    Args:
        block_text: Subtitle block text (with ID marker)
        target_language: Target language
        max_retry: Maximum number of retry attempts
        
    Returns:
        Translated subtitle block text (with ID marker)
    """
    template = """
    You are a professional subtitle translator fluent in {target_language}, especially skilled at translating conversational content into accurate and natural subtitles.

    Rules:
    - Accurately convey facts, context, and emotions from the original text
    - Preserve technical terms, brand names, and person names
    - Make translations conform to {target_language} expression habits
    - Keep subtitles concise for quick reading by viewers
    - Each subtitle block has a unique identifier like [BLOCK_1], [BLOCK_2], etc., which must be preserved during translation
    - Only translate the parts marked as "Need to translate", the parts marked as "Context" are for reference only and should not be translated
    - Maintain the original number and order of paragraphs
    - Only return translation results, don't include any explanations or original text

    Below is the subtitle content, where the "Need to translate" part needs translation, and the "Context" part is provided for reference:

    {text}
    
    Translation result (only return translation results for the "Need to translate" part):
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # Initialize LangChain model and chain
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.4,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    )
    
    # Use RunnableSequence instead of LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # Add retry logic
    retry_count = 0
    while retry_count < max_retry:
        try:
            translated_text = chain.invoke({"text": block_text, "target_language": target_language})
            if translated_text:
                return translated_text.strip()
        except Exception:
            pass
        retry_count += 1
    
    return ""


def extract_translations_by_id(translated_text: str) -> Dict[str, str]:
    """
    Extract translated text by block ID from translated batch text
    
    Args:
        translated_text: The translated text returned by the LLM
        
    Returns:
        Dictionary mapping block IDs to translated text
    """
    # Use regular expression to match text blocks starting with [BLOCK_number]
    pattern = r'\[BLOCK_(\d+)\]\s*\n([\s\S]*?)(?=\n\s*\[BLOCK_\d+\]|\s*$)'
    matches = re.findall(pattern, translated_text)
    
    result = {}
    for block_num, text in matches:
        block_id = f"BLOCK_{block_num}"
        result[block_id] = text.strip()
    
    return result


def translate_srt_file_by_block(input_path: str, output_path: str, log_file=None, target_language:str="Chinese", max_retry:int=5) -> str:
    """
    Translate SRT file block by block (fallback method)
    
    Args:
        input_path: Input SRT file path
        output_path: Output SRT file path
        log_file: Log file path
        target_language: Target language
        max_retry: Maximum retry attempts
        
    Returns:
        Output file path
    """
    print("Switching to block-by-block translation mode...")
    
    # Read SRT file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse SRT file
    subtitle_blocks = parse_srt(content)
    
    # Set up translation prompt template
    template = """
    You are a professional subtitle translator fluent in {target_language}, especially skilled at translating conversational content into accurate and natural subtitles.

    Rules:
    - Accurately convey facts, context, and emotions from the original text
    - Preserve technical terms, brand names, and person names
    - Make translations conform to {target_language} expression habits
    - Keep subtitles concise for quick reading by viewers
    - Only return translation results, don't include any explanations or original text

    Please translate the following English subtitle into {target_language}:

    {text}
    
    Translation result:
    """
    
    prompt = PromptTemplate(
        input_variables=["text", "target_language"],
        template=template
    )
    
    # Initialize LangChain model and chain
    llm = ChatDeepSeek(
        model="deepseek-reasoner",
        temperature=0.6,
        max_tokens=None,
        timeout=None,
        max_retries=3,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        # other params...
    )
    
    # Use RunnableSequence instead of LLMChain
    chain = prompt | llm | StrOutputParser()
    
    # Translate each subtitle block
    translated_blocks = []
    
    if log_file:
        log_mode = 'a' if os.path.exists(log_file) else 'w'
        with open(log_file, log_mode, encoding='utf-8') as f:
            f.write("=== Block-by-block translation mode ===\n\n")
    
    # Track failed translation blocks
    failed_blocks = 0
    
    for i, (idx, timestamp, text) in enumerate(subtitle_blocks):
        print(f"Translating subtitle block {i+1}/{len(subtitle_blocks)} (ID: {idx})...")
        
        # Add retry logic
        block_retry_count = 0
        block_successful = False
        translated_text = text  # Default to use original text
        
        while block_retry_count < max_retry and not block_successful:
            try:
                # Call model for translation
                print(f"Translation attempt {block_retry_count + 1}/{max_retry} for block {i+1}...")
                translated_text = chain.invoke({"text": text, "target_language": target_language})
                translated_text = translated_text.strip()
                
                # Check if translation is valid (at least not empty)
                if translated_text:
                    block_successful = True
                else:
                    print(f"Block {i+1} translation is empty, retrying...")
                    block_retry_count += 1
            except Exception as e:
                print(f"Block {i+1} translation error: {str(e)}, retrying...")
                block_retry_count += 1
        
        # If all retries fail
        if not block_successful:
            print(f"All translation attempts for block {i+1} failed!")
            failed_blocks += 1
        
        # Record log
        if log_file:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"Subtitle block {i+1} (ID: {idx}):\nOriginal: {text}\nTranslation: {translated_text}\n\n")
        
        # Add translated subtitle block to result list
        translated_blocks.append((idx, timestamp, translated_text))
    
    # Check if translation failed for most blocks
    if failed_blocks > len(subtitle_blocks) * 0.5:  # If more than half of blocks fail translation
        print(f"Warning: More than half of subtitle blocks failed translation ({failed_blocks}/{len(subtitle_blocks)})!")
        print("Translation quality may not be acceptable, translation aborted.")
        return ""
    
    # Recombine translated subtitle blocks into SRT format
    translated_content = format_srt(translated_blocks)
    
    # Write output file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)
    
    print(f"Block-by-block translation complete! Saved to: {output_path}")
    print(f"Successfully translated: {len(subtitle_blocks) - failed_blocks}/{len(subtitle_blocks)} subtitle blocks")
    if log_file:
        print(f"Translation log saved to: {log_file}")
    
    return output_path


def parse_srt(content: str) -> List[Tuple[str, str, str]]:
    """
    Parse SRT file content
    
    Args:
        content: SRT file content
        
    Returns:
        List of tuples (index, timestamp, text)
    """
    # Use regular expression to match SRT file parts
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
    translate_srt_file("resources/transcripts/zUyH3XhpLTo.srt", "resources/transcripts/zUyH3XhpLTo_cn.srt", log_file="translation_log.txt", max_retry=5)