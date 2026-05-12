from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

writer_prompt = """
1. Give me only the first nontrivial idea needed to solve this problem
2. DO NOT CONTINUE TO THE SOLUTION
3. End your response after the first insight

"""

critic_prompt = """
1. DO NOT PROPOSE A REPLACEMENT SOLUTION FOR THIS PROBLEM
2. Give pros and cons of idea
3. Identify errors, unjustified steps, hidden assumptions, and logical gaps
4. Test edge cases and counterexamples
5. Verify algebra, calculus, probability
6. Identify where rigor is missing

This is the problem and idea:
"""

judge_prompt = """
1. DO NOT PROPOSE A REPLACEMENT SOLUTION FOR THIS PROBLEM
2. Tell me if this idea is mathematically valid
3. Determine if proof in the right idea

This is the problem, idea, and critiques:
"""
question = r"""
"Let $f \colon \mathbb{Z}_{\geq 1} \to \mathbb{Z}_{\geq 1}$ be a function such that for all positive integers $m$ and $n$, 
\begin{equation*}
    f(m) + f(n) = f(m + n + mn).
\end{equation*}
Across all functions $f$ such that $f(n) \leq 1000$ for all $n \leq 1000$, how many different values can $f(2024)$ take?"
"""
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

writer_response = client.chat.completions.create(
    model="baidu/cobuddy:free",
    messages=[
        {"role": "user", "content": writer_prompt + question}
    ],
)

print(writer_response.choices[0].message.content)
critic_prompt = client.chat.completions.create(
    model="baidu/cobuddy:free",
    messages=[
        {"role": "user", "content": critic_prompt + question + "\n" + writer_response.choices[0].message.content}
    ],
)

print(critic_prompt.choices[0].message.content)

judge_prompt = client.chat.completions.create(
    model="baidu/cobuddy:free",
    messages=[
        {"role": "user", "content": judge_prompt + question + "\n" + writer_response.choices[0].message.content + "\n" + critic_prompt.choices[0].message.content}
    ],
)
print(judge_prompt.choices[0].message.content)
