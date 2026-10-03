import random
import json
import uuid
import google.generativeai as genai
import config

# Configure the Gemini API client if an API key is provided
if config.GEMINI_API_KEY and config.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" and len(config.GEMINI_API_KEY.strip()) > 0:
    genai.configure(api_key=config.GEMINI_API_KEY)
    gemini_configured = True
    print(f"✨ Gemini API configured successfully. Using model: {config.GEMINI_MODEL}")
else:
    gemini_configured = False
    print("⚠️ Warning: GEMINI_API_KEY is not configured. Running in Mock API Mode.")


# Mock Database of sentences to make the bot feel real during local testing if API is disabled
MOCK_TENSE_TASKS = {
    "Present Simple": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "She ___ (to like) reading books before sleeping.",
            "correct_answer": "likes"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "Water boils at 100 degrees Celsius.",
            "correct_answer": "Present Simple"
        }
    ],
    "Present Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "Look! The children ___ (to play) in the garden right now.",
            "correct_answer": "are playing"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "I am working on a new software project this week.",
            "correct_answer": "Present Continuous"
        }
    ],
    "Present Perfect": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "They ___ (to visit) Paris three times already.",
            "correct_answer": "have visited"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "She has just finished writing her monthly report.",
            "correct_answer": "Present Perfect"
        }
    ],
    "Present Perfect Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "I ___ (to learn) English for five years now.",
            "correct_answer": "have been learning"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "It has been raining all morning, and the ground is still wet.",
            "correct_answer": "Present Perfect Continuous"
        }
    ],
    "Past Simple": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "We ___ (to go) to the cinema yesterday evening.",
            "correct_answer": "went"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "He bought a new car last month.",
            "correct_answer": "Past Simple"
        }
    ],
    "Past Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "He ___ (to sleep) when I called him.",
            "correct_answer": "was sleeping"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "We were eating dinner while they were watching television.",
            "correct_answer": "Past Continuous"
        }
    ],
    "Past Perfect": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "The train ___ (to leave) before we arrived at the platform.",
            "correct_answer": "had left"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "She had already cleaned the house when her guests arrived.",
            "correct_answer": "Past Perfect"
        }
    ],
    "Past Perfect Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "They ___ (to walk) for hours before they finally saw the hotel.",
            "correct_answer": "had been walking"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "He was exhausted because he had been working out since morning.",
            "correct_answer": "Past Perfect Continuous"
        }
    ],
    "Future Simple": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "I think it ___ (to rain) tomorrow, so bring an umbrella.",
            "correct_answer": "will rain"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "I will open the window for you, it is too hot here.",
            "correct_answer": "Future Simple"
        }
    ],
    "Future Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "This time tomorrow, we ___ (to fly) to London.",
            "correct_answer": "will be flying"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "He will be presenting his slides during the 3 PM meeting.",
            "correct_answer": "Future Continuous"
        }
    ],
    "Future Perfect": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "By next week, she ___ (to complete) her online course.",
            "correct_answer": "will have completed"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "They will have built the new bridge by the end of this year.",
            "correct_answer": "Future Perfect"
        }
    ],
    "Future Perfect Continuous": [
        {
            "task_type": "fill_in_the_blank",
            "sentence": "By next July, he ___ (to live) in this city for a decade.",
            "correct_answer": "will have been living"
        },
        {
            "task_type": "guess_the_tense",
            "sentence": "She will have been teaching at the university for 20 years by her retirement.",
            "correct_answer": "Future Perfect Continuous"
        }
    ],
}


async def generate_word_details(word: str) -> dict:
    """
    Generates word translation and description/context.
    Queries Gemini API if configured; otherwise falls back to mock responses.
    """
    word_lower = word.strip().lower()
    
    if not gemini_configured:
        # Fallback to local mock translations
        mock_translations = {
            "ubiquitous": ("всюдисущий / повсюдний", "He wants to be ubiquitous, appearing everywhere at once."),
            "reluctance": ("неохота / небажання", "She showed great reluctance to answer my questions."),
            "serendipity": ("інтуїтивна прозорливість / щасливий випадок", "We found the charming cafe by pure serendipity."),
            "meticulous": ("ретельний / дріб'язковий", "He is meticulous about keeping his room clean."),
        }
        if word_lower in mock_translations:
            translation, description = mock_translations[word_lower]
        else:
            translation = f"Переклад слова '{word}'"
            description = f"Example sentence: This is how you use the word '{word}' in a daily conversation."
            
        return {
            "translation": translation,
            "description": description
        }
        
    # Build a structured system prompt for translation
    prompt = (
        f"You are a helpful translation assistant. Translate the English word or phrase '{word}' to Ukrainian "
        f"and provide a brief example sentence of how to use it in daily conversation.\n"
        f"Format your output as a raw JSON object with exactly two keys:\n"
        f"\"translation\": the translation in Ukrainian\n"
        f"\"description\": the example sentence in English with Ukrainian translation in brackets.\n\n"
        f"Example output format:\n"
        f"{{\n"
        f"  \"translation\": \"всюдисущий\",\n"
        f"  \"description\": \"He wants to be ubiquitous, appearing everywhere at once. (Він хоче бути всюдисущим, з'являючись усюди одночасно.)\"\n"
        f"}}\n\n"
        f"Provide ONLY the raw JSON object, without any markdown code block formatting (do not wrap in ```json)."
    )
    
    try:
        # Load the model and make the call asynchronously
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        
        # Clean any markdown formatting if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            text = "\n".join(lines)
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        return {
            "translation": data.get("translation", f"Переклад '{word}'"),
            "description": data.get("description", "No example sentence provided.")
        }
    except Exception as e:
        print(f"Error calling Gemini in generate_word_details: {e}")
        return {
            "translation": f"Помилка перекладу ({word})",
            "description": f"Could not generate context due to an error: {e}"
        }


async def verify_translation(word: str, correct_translation: str, user_translation: str) -> bool:
    """
    Verifies if user's translation is correct, a valid synonym, or an acceptable variation using Gemini.
    Returns True if Gemini answers YES, otherwise False.
    """
    if not gemini_configured:
        return False
        
    prompt = (
        f"You are a lenient language teacher. The expected translation is '{correct_translation}' and the user typed '{user_translation}'.\n"
        f"Rule 1: Accept minor typos (1-2 letters wrong).\n"
        f"Rule 2: Accept different parts of speech (e.g., if the user types a noun but the answer is a verb, like 'результат' instead of 'призводити', accept it if the core root meaning is the same).\n"
        f"Rule 3: Accept valid synonyms.\n"
        f"Reply ONLY with 'YES' if it passes these rules, or 'NO'."
    )
    
    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = await model.generate_content_async(prompt)
        text = response.text.strip().upper()
        return "YES" in text
    except Exception as e:
        print(f"Error calling Gemini in verify_translation: {e}")
        return False



async def generate_tense_task(tense_name: str, task_type: str) -> dict:
    """
    Generates a fill-in-the-blank or guess-the-tense task for the specified tense.
    Queries Gemini API if configured; otherwise falls back to random mock questions.
    """
    import random

    characters = [
        "a clumsy spy",
        "a lazy astronaut",
        "an overly dramatic chef",
        "a time-traveling historian",
        "a grumpy wizard",
        "a retired superhero",
        "a paranoid detective"
    ]
    settings = [
        "on a spaceship",
        "in a medieval village",
        "during a zombie apocalypse",
        "at a bizarre cooking competition",
        "in a secret underground lab",
        "at a magical academy"
    ]

    selected_character = random.choice(characters)
    selected_setting = random.choice(settings)

    if not gemini_configured:
        # Fallback to local mock tasks matching the requested task_type
        tasks = MOCK_TENSE_TASKS.get(tense_name)
        if not tasks:
            return {
                "task_type": task_type,
                "sentence": "I ___ (to go) to school every day." if task_type == "fill_in_the_blank" else "I go to school every day.",
                "correct_answer": "go" if task_type == "fill_in_the_blank" else tense_name
            }
        filtered_tasks = [t for t in tasks if t["task_type"] == task_type]
        if filtered_tasks:
            return random.choice(filtered_tasks)
        return random.choice(tasks)
        
    prompt = (
        f"You are an English teacher. Generate a practice task for the tense: '{tense_name}'.\n"
        f"The task type MUST be exactly '{task_type}'.\n\n"
        f"Write the sentence about '{selected_character}' who is '{selected_setting}'. You MUST strictly follow this topic. DO NOT use generic names like Sarah or John.\n\n"
        f"The English level MUST be exactly B2 (Upper-Intermediate). Use clear, practical, and everyday B2 vocabulary. DO NOT use C1/C2 words, obscure idioms, or complex literary language. The sentence must be easy for a B2 learner to understand.\n\n"
        f"Instructions for each task type:\n"
        f"1. If task type is 'fill_in_the_blank': Generate a sentence with a blank marked as \"___\" and the base verb in brackets, e.g. \"He ___ (to sleep) when I called.\"\n"
        f"2. If task type is 'guess_the_tense': Generate a complete sentence where the user needs to guess that the tense is \"{tense_name}\".\n\n"
        f"Format your output as a raw JSON object with exactly three keys:\n"
        f"\"task_type\": must be exactly the string \"{task_type}\"\n"
        f"\"sentence\": the question sentence to show to the user\n"
        f"\"correct_answer\": the correct answer. For \"fill_in_the_blank\", it must be just the correct verb form (e.g., \"was sleeping\"). "
        f"For \"guess_the_tense\", it must be exactly the string \"{tense_name}\".\n\n"
        f"Example output format for \"fill_in_the_blank\":\n"
        f"{{\n"
        f"  \"task_type\": \"fill_in_the_blank\",\n"
        f"  \"sentence\": \"The clumsy spy ___ (to drop) his secret documents on the floor.\",\n"
        f"  \"correct_answer\": \"dropped\"\n"
        f"}}\n\n"
        f"Example output format for \"guess_the_tense\":\n"
        f"{{\n"
        f"  \"task_type\": \"guess_the_tense\",\n"
        f"  \"sentence\": \"The lazy astronaut was sleeping while the spaceship was orbiting the moon.\",\n"
        f"  \"correct_answer\": \"{tense_name}\"\n"
        f"}}\n\n"
        f"Provide ONLY the raw JSON object, without any markdown formatting."
    )
    
    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = await model.generate_content_async(prompt)
        text = response.text.strip()
        
        # Clean any markdown formatting if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            text = "\n".join(lines)
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        return {
            "task_type": task_type,
            "sentence": data.get("sentence", "I ___ (to study) grammar." if task_type == "fill_in_the_blank" else "I study grammar."),
            "correct_answer": data.get("correct_answer", "study" if task_type == "fill_in_the_blank" else tense_name)
        }
    except Exception as e:
        print(f"Error calling Gemini in generate_tense_task: {e}")
        return {
            "task_type": task_type,
            "sentence": f"API Error: We ___ (to struggle) with connectivity. Details: {e}" if task_type == "fill_in_the_blank" else f"API Error: We struggle with connectivity. Details: {e}",
            "correct_answer": "struggled" if task_type == "fill_in_the_blank" else tense_name
        }


async def explain_tense_mistake(tense_name: str, sentence: str, correct_answer: str, user_answer: str) -> str:
    """
    Generates a brief explanation in Ukrainian explaining why the user's answer is wrong.
    Queries Gemini API if configured; otherwise returns standard text.
    """
    if not gemini_configured:
        explanation = (
            f"Ваша відповідь '{user_answer}' не є правильною для речення:\n"
            f"\"{sentence}\"\n\n"
            f"Правильна відповідь: '{correct_answer}'.\n"
            f"У {tense_name} ми використовуємо цю форму, щоб відобразити правильний часовий зв'язок між діями."
        )
        return explanation
        
    prompt = (
        f"You are an English grammar tutor. A student made a mistake in a task for the tense '{tense_name}'.\n"
        f"Sentence: \"{sentence}\"\n"
        f"Correct answer: \"{correct_answer}\"\n"
        f"Student's wrong answer: \"{user_answer}\"\n\n"
        f"Briefly explain to the student in Ukrainian why their answer is wrong, and why the correct answer is appropriate. "
        f"Keep the explanation short, simple, and friendly (max 3-4 sentences).\n\n"
        f"IMPORTANT RULES FOR YOUR RESPONSE:\n"
        f"1. DO NOT use any markdown formatting (absolutely no asterisks ** or underscores _). If you need to emphasize a word or phrase, you MUST use HTML bold tags (e.g., <b>word</b>).\n"
        f"2. Write in natural, grammatically correct Ukrainian. Address the user directly using the masculine gender (e.g., use 'ти використав', NEVER use awkward forms like 'використазив(-ла)' or 'зробив/ла').\n"
        f"3. DO NOT use any greetings (like 'Привіт', 'Вітаю', 'Hello'). Start your text directly with the explanation of the mistake."
    )
    
    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error calling Gemini in explain_tense_mistake: {e}")
        return f"Помилка отримання пояснення від ШІ: {e}. Правильна відповідь: '{correct_answer}'."
