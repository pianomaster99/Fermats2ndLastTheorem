from graph_of_thoughts.operations.thought import Thought
import json

from sklearn.neural_network import MLPClassifier

model = MLPClassifier(
    hidden_layer_sizes=(10,),
    activation="relu",
    max_iter=1000,
    random_state=42
)

#We are defining an agent that takes in 5 evaluator scores and outputs binary 0 or 1
#0 if proof is on the right path, 1 if proof is not on the right path
#this will be done supervised