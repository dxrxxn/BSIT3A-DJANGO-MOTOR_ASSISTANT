# MOTOR_ASSISTANT


# DEVELOPMENT OF A WEB-BASED MOTORCYCLE AND VEHICLE DIAGNOSTIC ASSISTANT WITH GUIDED TROUBLESHOOTING AND AI-SUPPORTED REPAIR GUIDANCE

**BSIT Capstone Project Concept Paper**

---

## INTRODUCTION

### Background of the Project
Motorcycle and vehicle owners may have difficulty identifying the possible causes of mechanical problems, especially when they have limited access to a mechanic or reliable repair information. Symptoms such as difficulty starting, unusual engine sounds, overheating, and brake problems may have several possible causes[cite: 3]. Searching online for answers can also be challenging because the information may be too technical, may not apply to the user’s specific vehicle, or may not clearly explain when professional assistance is needed[cite: 3].

To address these concerns, this project will develop a web-based Motorcycle and Vehicle Diagnostic Assistant[cite: 3]. The system will guide users through questions about their vehicle and reported symptoms, then provide possible causes and troubleshooting guidance based on its diagnostic knowledge base[cite: 3]. When configured, an AI service will help generate responses using available diagnostic information[cite: 3]. The system will also provide safety alerts for selected critical symptoms and will support diagnostic conversations in English, Filipino/Tagalog, and Hiligaynon/Ilonggo[cite: 3]. It will present its guidance as informational support and will not treat possible causes as confirmed diagnoses[cite: 3].

### Statement of the Problem or Project Objectives
The main objective of this project will be to design, develop, and evaluate a web-based Motorcycle and Vehicle Diagnostic Assistant that will help users understand common vehicle symptoms through guided troubleshooting and AI-supported repair guidance[cite: 3].

Specifically, the project will:
1. Develop a guided diagnostic workflow that will collect vehicle details and symptom information through follow-up questions[cite: 3].
2. Provide access to diagnostic information containing vehicle symptoms, possible causes, diagnostic checks, and troubleshooting guidance[cite: 3].
3. Integrate an AI-supported response feature that will use available diagnostic information to help explain possible causes and troubleshooting steps[cite: 3].
4. Provide safety alerts for selected critical symptoms and advise users to stop using the vehicle and seek professional assistance when appropriate[cite: 3].
5. Provide authenticated users with diagnostic conversation history and an optional photo-upload feature, subject to system and AI-provider configuration[cite: 3].
6. Support English, Filipino/Tagalog, and Hiligaynon/Ilonggo in applicable diagnostic questions and responses[cite: 3].
7. Conduct user acceptance testing with selected vehicle owners, riders, or mechanics to evaluate the system’s usability, clarity, and usefulness[cite: 3].

### Significance of the Project
The proposed system will provide practical value to the following beneficiaries[cite: 3]:
* **Motorcycle and Vehicle Owners:** The system will help users describe vehicle symptoms, answer relevant diagnostic questions, and review possible causes and troubleshooting information[cite: 3].
* **Motorcycle Riders:** The safety alerts will help riders recognize selected symptoms that may require them to stop using the vehicle and consult a qualified mechanic[cite: 3].
* **Mechanics and Repair Personnel:** The information gathered through the guided diagnostic process will help users describe their vehicle and reported symptoms when seeking professional assistance[cite: 3].
* **Students and Future Researchers:** The project will serve as a reference for future studies involving web-based diagnostic systems, guided troubleshooting, and AI-supported information services[cite: 3].

### Alignment with Institutional Research Agenda and Sustainable Development Goals
* **Institutional Research Agenda Alignment:** The project will support the institutional research priority related to Information Technology through the development of a web-based application that will apply software development and AI-supported features to vehicle diagnostic information[cite: 3]. The specific research-priority name will follow the institution’s officially approved agenda[cite: 3].
* **Sustainable Development Goal Alignment:**
  * **SDG 9 (Industry, Innovation, and Infrastructure):** The project will apply web technologies and AI-supported features to create a digital tool for accessing vehicle diagnostic information[cite: 3].
  * **SDG 3 (Good Health and Well-Being):** The system will provide safety-oriented alerts for selected critical vehicle symptoms and will encourage users to seek qualified professional assistance when appropriate[cite: 3]. The system will not certify vehicle safety or replace a professional inspection[cite: 3].

---

## SCOPE AND LIMITATIONS

### System Scope and Technical Architecture

| Component | Description and Coverage |
| :--- | :--- |
| **Core modules** | The system will include user authentication, guided vehicle and symptom intake, diagnostic conversations, a diagnostic knowledge base, safety alerts, conversation history, optional diagnostic photo uploads, and an interactive 3D motorcycle viewer. |
| **Technology stack** | The system will use Python and Django for backend processing, SQLite or MySQL/MariaDB for database management, and HTML, CSS, and JavaScript for the web interface. |
| **Target users** | The intended users will include motorcycle and vehicle owners, riders, mechanics, repair personnel, and authorized system administrators. |
| **Deployment** | The system will be accessible through a web browser and will require an appropriate local or hosted server. |

### Limitations
* The system will provide informational diagnostic support and will not provide a confirmed diagnosis, replace a qualified mechanic, or substitute for a physical vehicle inspection[cite: 3].
* The system’s diagnostic coverage will be limited to the symptoms, questions, and guidance available in its knowledge base[cite: 3].
* The accuracy and relevance of guidance will depend on the quality and completeness of the available diagnostic records[cite: 3].
* AI-generated responses may be incomplete or inaccurate[cite: 3]. Vehicle-specific specifications, repair procedures, and part compatibility will require verification using appropriate sources or professional expertise[cite: 3].
* Photo analysis will depend on whether the selected AI provider and system configuration support image input[cite: 3]. A photo alone will not confirm the cause of a vehicle problem[cite: 3].
* The system will not connect to vehicle sensors, onboard diagnostic equipment, or live vehicle data[cite: 3].
* The 3D viewer will display only the components included in its available motorcycle model and will not represent every vehicle component[cite: 3].
* The system will not perform repairs or guarantee that a vehicle is safe to operate[cite: 3].
