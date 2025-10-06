# Fine-Tuning Flow Diagrams

## Diagrams Overview

#### Part 1: Data Preparation & Model Setup
[![Data Preparation & Model Setup](https://www.plantuml.com/plantuml/proxy?cache=no&src=https://raw.githubusercontent.com/vgu-its24-psd/MedDiag/main/fine_tunning/1_data_preparation_and_model_setup.puml)](1_data_preparation_and_model_setup.puml)

**Covers:**
- Setup & Configuration (HuggingFace, dependencies, Google Drive)
- Data Preparation (clinical CSV + medical images → 116 samples)
- Model Loading (4-bit quantization with BitsAndBytes)
- LoRA Configuration (PEFT setup)
- Custom Data Collation

#### Part 2: Training Process
[![Training Process](https://www.plantuml.com/plantuml/proxy?cache=no&src=https://raw.githubusercontent.com/vgu-its24-psd/MedDiag/main/fine_tunning/2_training_process.pu)](2_training_process.puml)

**Covers:**
- Training Configuration (SFTConfig hyperparameters)
- QLoRA Fine-Tuning Loop (batch processing, forward/backward pass)
- Parameter Updates (LoRA adapters only)
- Checkpoint Saving & Hub Deployment
