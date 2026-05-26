from openai import OpenAI
from dotenv import load_dotenv
import os
from app.schemas.analysis import BAAnalysisOutput

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_transcript(transcript: str) -> BAAnalysisOutput:
   completion = client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        messages=[
            {
             "role": "system",
             "content": """
                You are a senior enterprise Business Analyst.

                Extract only implementation-relevant information.
                Separate confirmed facts from assumptions.
                Do not invent missing requirements.
                Identify ambiguity, risks, dependencies, open questions,
                user stories, acceptance criteria, functional requirements,
                assumptions, and UAT scenarios.
                """
            },
            {
              "role": "user",
              "content": f"Analyze this meeting transcript:\n\n{transcript}"
            }
        ],
        response_format=BAAnalysisOutput,
   )
   return completion.choices[0].message.parsed

# prompt = f"""
  #    Act as a senior enterprise Business Analyst.
#    Analyze this meeting transcript and extract:
#    - Business summary
#    - User stories
#    - Acceptance criteria
  #  - Risks
  #  - Assumptions
  #  - Dependencies
  #  - Open questions
  #  - UAT scenarios

#  Transcript:
  #  {transcript}
#    response = client.chat.completions.create(
  #      model="gpt-4.1-mini",
        #model="gpt-5-nano",
  #      messages=[
   ##         {"role": "system", "content": "You are a senior business analyst."},
   #         {"role": "user", "content": prompt}
   #     ]
#  )
#    return response.choices[0].message.parsed
