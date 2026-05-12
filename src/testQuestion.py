from openai import OpenAI
from dotenv import load_dotenv
import time
import os

load_dotenv()

model_type = "arcee-ai/trinity-large-thinking:free"

writer_prompt = """
You are a mathematical hint generator.

Give ONLY the first conceptual insight needed to begin the problem.

DO NOT:
- derive consequences of the idea,
- simplify the problem fully,
- compute bounds,
- introduce constructions,
- classify cases,
- give the final answer,
- continue after the initial observation.

Your response must:
- be at most 2 sentences,
- contain exactly one idea,
- stop before any substantial derivation begins.

If you find yourself proving something or reducing the problem to computation, stop immediately.
"""

critic_prompt = """
You are a mathematical critic.

Your only task is to determine whether the proposed idea/proof is mathematically valid.

Do not propose a new solution.
Do not continue the proof.

Identify:
- logical gaps,
- unjustified assumptions,
- incorrect deductions,
- invalid computations,
- missing rigor.

Be precise and skeptical.

This is the problem and proposed idea:
"""

judge_prompt = """
You are a mathematical judge.

Your only task is to determine whether the proposed idea is fundamentally moving in the correct direction.

Do not solve the problem.
Do not provide a replacement strategy.

Think about
1. Is the core idea promising?
2. Is the reasoning directionally correct?

Give simply yes or no on whether to continue with the idea

Focus on high-level mathematical validity rather than details.

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
start = time.time()

writer_response = client.chat.completions.create(
    model=model_type,
    messages=[
        {"role": "user", "content": writer_prompt + question}
    ],
    extra_body={
        "reasoning": {
            "effort": "minimal"
        }
    }
)
writer_end = time.time()
print(writer_end - start)
print(writer_response.choices[0].message.content)
critic_prompt = client.chat.completions.create(
    model=model_type,
    messages=[
        {"role": "user", "content": critic_prompt + question + "\n" + writer_response.choices[0].message.content}
    ],
)
critic_end = time.time()
print(critic_end - writer_end)
print(critic_prompt.choices[0].message.content)

judge_prompt = client.chat.completions.create(
    model=model_type,
    messages=[
        {"role": "user", "content": judge_prompt + question + "\n" + writer_response.choices[0].message.content + "\n" + critic_prompt.choices[0].message.content}
    ],
)

judge_end = time.time()
print(judge_end - critic_end)
print(judge_prompt.choices[0].message.content)
