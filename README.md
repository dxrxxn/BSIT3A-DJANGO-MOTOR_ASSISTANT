# MOTOR_ASSISTANT

## Project Documentation

Maaari mong basahin ang buong concept paper sa ibaba, o i-download ang orihinal na file sa pamamagitan ng link na ito:
- **[I-download ang BSIT Capstone Project Concept Paper (DOCX)](docs/A%20WEB-BASED%20MOTORCYCLE%20DIAGNOSTIC%20ASSISTANT%20WITH%20GUIDED%20TROUBLESHOOTING%20AND%20AI-SUPPORTED%20REPAIR%20GUIDANCE.docx)**

---

# A WEB-BASED MOTORCYCLE DIAGNOSTIC ASSISTANT WITH GUIDED TROUBLESHOOTING AND AI-SUPPORTED REPAIR GUIDANCE
**BSIT Capstone Project Concept Paper**

## INTRODUCTION

### Background of the Project
Motorcycle and vehicle owners frequently encounter mechanical problems that are difficult to identify without professional mechanical knowledge or access to a qualified mechanic[cite: 5]. Common symptoms such as difficulty starting, unusual engine sounds, overheating, brake failures, and electrical irregularities may have multiple potential causes, and misdiagnosis can lead to further vehicle damage or, in critical cases, personal injury[cite: 5]. In many communities, particularly those in rural or semi-urban areas in the Philippines, affordable and readily available automotive repair expertise remains limited[cite: 5].

When vehicle owners resort to searching for repair information online, they often encounter technical content that is not suited to their level of expertise, is not specific to their vehicle make, model, or year, or fails to clearly communicate when professional repair assistance is urgently required[cite: 5]. This informational gap leaves many owners either performing unsafe do-it-yourself repairs or neglecting vehicle problems altogether due to uncertainty about the root cause[cite: 5].

To address these concerns, the proposed project will develop a web-based Motorcycle and Vehicle Diagnostic Assistant[cite: 5]. The system will guide users through a structured series of questions about their reported vehicle symptoms and gather relevant vehicle details such as make, model, year, and fuel system type[cite: 5]. Based on the collected information, the system will provide possible causes and step-by-step troubleshooting guidance drawn from a curated diagnostic knowledge base[cite: 5]. When configured with an AI provider, the system will generate contextual repair guidance using the Google Gemini AI service[cite: 5]. The system will also issue safety alerts for selected critical symptoms and will support multilingual diagnostic conversations in English, Filipino/Tagalog, and Hiligaynon/Ilonggo[cite: 5]. All diagnostic outputs will be presented as informational support only and will not be treated as confirmed diagnoses or professional mechanical certifications[cite: 5].

### Statement of the Problem or Project Objectives
The main objective of this project will be to design, develop, and evaluate a web-based Motorcycle and Vehicle Diagnostic Assistant that will help users understand common vehicle symptoms through guided troubleshooting and AI-supported repair guidance[cite: 5].

Specifically, the project will accomplish the following technical objectives:
* **Develop a guided diagnostic workflow** that will collect vehicle details including vehicle type, make, model, year, variant, engine displacement, and fuel system along with reported symptom information through structured follow-up questions to progressively narrow down possible causes[cite: 5].
* **Build and maintain a structured diagnostic knowledge base** containing vehicle symptoms, associated possible causes, confidence levels, diagnostic tests, expected results, repair instructions, required parts, and safety precautions, accessible to the system's diagnostic engine for offline and AI-augmented responses[cite: 5].
* **Integrate an AI-supported response feature** using the Google Gemini API that will use available diagnostic knowledge base records as contextual input to generate clear, accurate, and vehicle-specific explanations of possible causes and troubleshooting steps[cite: 5].
* **Implement a safety alert mechanism** that will detect selected critical-urgency symptoms and immediately advise users to stop operating the vehicle and seek qualified professional mechanical assistance before any further action is taken[cite: 5].
* **Provide authenticated users** with persistent diagnostic conversation history, a conversation staging tracker, and an optional diagnostic photo-upload feature that users may submit alongside symptom descriptions for AI-assisted visual assessment, subject to system and AI provider configuration[cite: 5].
* **Support English, Filipino/Tagalog, and Hiligaynon/Ilonggo** in diagnostic questions, system messages, and applicable AI-generated responses to improve accessibility for Filipino vehicle owners and mechanics[cite: 5].
* **Implement role-based user access** and an AI usage tracking system that will monitor daily API request consumption and token usage against a configurable application budget, ensuring sustainable and auditable use of the integrated AI provider[cite: 5].
* **Conduct user acceptance testing (UAT)** with selected vehicle owners, motorcycle riders, and mechanics to evaluate the system's usability, diagnostic clarity, multilingual accessibility, and overall practical usefulness[cite: 5].

### Significance of the Project
The proposed system will provide direct practical value to the following beneficiaries[cite: 5]:
* **Motorcycle and Vehicle Owners:** The system will help users systematically describe vehicle symptoms, respond to guided diagnostic questions, and review possible causes and troubleshooting information in plain, accessible language[cite: 5]. It will reduce reliance on informal and potentially unreliable online sources[cite: 5].
* **Motorcycle Riders:** The safety alert mechanism will notify riders of selected symptoms that indicate serious mechanical risk, helping them make informed decisions about whether to continue operating the vehicle or seek immediate professional assistance, potentially preventing accidents caused by undetected vehicle failure[cite: 5].
* **Mechanics and Repair Personnel:** The guided diagnostic intake process will encourage vehicle owners to document their reported symptoms, vehicle details, and diagnostic observations in a structured format, enabling mechanics to receive more complete and organized problem descriptions when clients seek professional service[cite: 5].
* **Students and Future Researchers:** The project will serve as a reference framework for future studies involving web-based diagnostic systems, guided troubleshooting workflows, AI-augmented information services, and multilingual support in locally contextualized software applications[cite: 5].

### Alignment with Institutional Research Agenda and Sustainable Development Goals
* **Institutional Research Agenda Alignment:** The project will support the institutional research priority related to Information and Communications Technology by developing a web-based application that applies software engineering, AI-supported features, and structured knowledge management to vehicle diagnostic information for practical community use[cite: 5].
* **Sustainable Development Goal Alignment:**
  * **SDG 9 (Industry, Innovation, and Infrastructure):** The project will apply web technologies, a curated diagnostic knowledge base, and AI integration to create a digital tool that broadens access to vehicle diagnostic information, particularly for communities with limited access to professional automotive expertise[cite: 5].
  * **SDG 3 (Good Health and Well-Being):** The system will include safety-oriented alerts for selected critical vehicle symptoms and will consistently encourage users to seek qualified professional assistance when appropriate[cite: 5]. The system will not certify vehicle safety or substitute for a licensed mechanical inspection[cite: 5].

---

## SCOPE AND LIMITATIONS

### System Scope and Technical Architecture
| Component | Description and Coverage |
| :--- | :--- |
| **Core Modules** | The system will include user authentication and registration, guided vehicle and symptom intake, AI-augmented diagnostic conversations via the Gemini API, a structured diagnostic knowledge base with symptom records and troubleshooting guides, safety alert detection, persistent conversation history with staging and summary, optional diagnostic photo uploads, AI usage tracking, an offline knowledge cache for fallback responses, and an interactive 3D motorcycle component viewer[cite: 5]. |
| **Technology Stack** | The system will use Python and Django for backend processing, MySQL or SQLite for relational database management, and HTML5, CSS3, and JavaScript for the web interface[cite: 5]. The Gemini AI integration will be handled via the Google GenAI SDK[cite: 5]. The 3D viewer will utilize Three.js or a compatible JavaScript 3D rendering library[cite: 5]. |
| **Target Users** | The intended users will include motorcycle and vehicle owners, motorcycle riders, mechanics and repair personnel, and authorized system administrators[cite: 5]. |
| **Deployment** | The system will be accessible through a standard web browser and will require an appropriate local development server or hosted web server environment[cite: 5]. |

### Limitations
* The system will provide informational diagnostic support only[cite: 5]. It will not deliver a confirmed mechanical diagnosis, replace the judgment of a qualified mechanic, or serve as a substitute for a physical vehicle inspection[cite: 5].
* The system's diagnostic coverage will be limited to the symptoms, follow-up questions, and troubleshooting guides available in its knowledge base[cite: 5]. Symptoms not present in the knowledge base may not receive detailed offline guidance[cite: 5].
* The accuracy and relevance of diagnostic guidance will depend on the quality, completeness, and review status of available knowledge base records[cite: 5]. Only approved and verified troubleshooting guides will be retrieved for AI-augmented and offline responses[cite: 5].
* AI-generated responses may be incomplete, inaccurate, or not applicable to every vehicle configuration[cite: 5]. Vehicle-specific specifications, repair torque values, wiring diagrams, and part compatibility will require verification using appropriate manufacturer service manuals or professional expertise[cite: 5].
* The optional photo-upload and AI-assisted visual assessment feature will depend on whether the selected AI provider and the current system configuration support multimodal image input[cite: 5]. A submitted photo alone will not confirm the cause of a vehicle problem[cite: 5].
* The system will not connect to vehicle onboard diagnostic (OBD) ports, live vehicle sensors, or electronic control units[cite: 5]. All diagnostic input will be provided manually by the user through the web interface[cite: 5].
* The interactive 3D viewer will display only the motorcycle components included in its available 3D model assets and will not represent every vehicle variant, make, or component type[cite: 5].
* The system will not perform repairs, order replacement parts, or provide any assurance that a vehicle is safe to operate following user-performed maintenance[cite: 5].
* AI service availability will depend on the Google Gemini API configuration, daily application budget limits, and internet connectivity at the time of use[cite: 5].