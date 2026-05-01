from langchain_community.llms import Ollama

llm = Ollama(model="mistral")

resposta = llm.invoke("Explique o que é gripe")

print(resposta)
