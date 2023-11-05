"""Generic agent."""

from typing import List
from pydantic import BaseModel, Field

from langchain.tools import Tool
from langchain.agents import AgentExecutor
from langchain.chat_models import ChatOpenAI as OpenAI
from langchain.tools.render import render_text_description
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents.output_parsers import ReActSingleInputOutputParser, PydanticOutputParser

from .prompts import Prompts
from .agent.agent_vote import AgentVote

class Agent(BaseModel):
	"""Generic agent implementation."""
	role: str = Field(description="Role of the agent")
	goal: str = Field(description="Objective of the agent")
	backstory: str = Field(description="Backstory of the agent")
	tools: List[Tool] = Field(
		description="Tools at agents disposal",
		default=[]
	)
	prompts: Prompts = Field(
		description="Prompts class for the agent.",
		default=Prompts
	)
	llm: str = Field(
		description="LLM of the agent", 
		default=OpenAI(
			temperature=0.7,
			model="gpt-4",
			verbose=True
		)
	)
  
	def vote_agent_for_task(self, task: str) -> AgentVote:
		"""
		Execute a task with the agent.
			Parameters:
				task (str): Task to execute
			Returns:
				output (AgentVote): The agent voted to execute the task
		"""
		parser = PydanticOutputParser(pydantic_object=AgentVote)
		prompt = Prompts.AGENT_EXECUTION_PROMPT.partial(
			tools=render_text_description(self.tools),
			tool_names=self.__tools_names(),
			backstory=self.backstory,
			role=self.role,
			goal=self.goal,
			format_instructions=parser.get_format_instructions()
		)
		return self.__function_calling(task, prompt, parser)

	def execute_task(self, task: str) -> str:
		"""
		Execute a task with the agent.
			Parameters:
				task (str): Task to execute
			Returns:
				output (str): Output of the agent
		"""
		prompt = Prompts.AGENT_EXECUTION_PROMPT.partial(
			tools=render_text_description(self.tools),
			tool_names=self.__tools_names(),
			backstory=self.backstory,
			role=self.role,
			goal=self.goal,
		)
		return self.__execute_task(task, prompt)

	def __function_calling(self, input: str, prompt: str, parser: str) -> str:
		inner_agent = {
			"input": lambda x: x["input"],
			"agent_scratchpad": lambda x: format_log_to_str(x['intermediate_steps'])
		} | prompt | parser
		
		return self.__execute(inner_agent, input)
		
	def __execute_task(self, input: str, prompt: str) -> str:
		chat_with_bind = self.llm.bind(stop=["\nObservation"])
		inner_agent = {
			"input": lambda x: x["input"],
			"agent_scratchpad": lambda x: format_log_to_str(x['intermediate_steps'])
		} | prompt | chat_with_bind | ReActSingleInputOutputParser()

		return self.__execute(inner_agent, input)

	def __execute(self, inner_agent, input):
		agent_executor = AgentExecutor(
			agent=inner_agent,
			tools=self.tools,
			verbose=True,
			handle_parsing_errors=True
		)
		return agent_executor.invoke({"input": input})['output']

	def __tools_names(self) -> str:
		return ", ".join([t.name for t in self.tools])
	