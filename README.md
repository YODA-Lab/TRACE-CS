# TRACE-CS
This repository contains the code for the TRACE-CS framework, presented in the AAAI 2025 demo paper: [Trustworthy Reasoning for Contrastive Explanations in Course Scheduling Problems](https://arxiv.org/abs/2409.03671).

## Overview

TRACE-CS is a hybrid system that combines symbolic reasoning and large language models (LLMs) to provide contrastive explanations in course scheduling. By leveraging SAT-solving techniques and the natural language generation capabilities of LLMs, TRACE-CS ensures:
- Accurate and provably correct explanations.
-	Linguistically coherent and user-friendly communication.
-	Support for real-world course scheduling scenarios.

#### Key Feautures:

- **Symbolic Module**: Encodes scheduling constraints and generates logic-based explanations.
- **LLM Module**: Converts user queries to symbolic representations and refines explanations into natural language.

#### Installation:

Clone the repository:

    git clone https://github.com/YODA-Lab/TRACE-CS/

Navigate to the project directory:

    cd trace-cs

Install dependencies: 

    pip install -r requirements.txt

 #### Usage
To launch the GUI, simply run:

    python main.py


### Citation
If you use TRACE-CS, or you are inspired by TRACE-CS, please cite the paper:

    @inproceedings{trace-cs2025,
      title={Trustworthy Reasoning for Contrastive Explanations in Course Scheduling Problems},
      author={Stylianos Loukas Vasileiou, William Yeoh},
      booktitle={Proceedings of the AAAI Conference on Artificial Intelligence},
      year={2025}
    }


#### License
This project is licensed under the MIT License.
 
 
  


