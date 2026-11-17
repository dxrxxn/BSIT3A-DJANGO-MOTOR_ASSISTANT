# MOTOR_ASSISTANT

# A Web-Based Motorcycle Diagnostic Assistant with Guided Troubleshooting and AI-Supported Repair Guidance

> 📄 **[Download Full Concept Paper (.docx)]/docs/Concept_Paper.docx)**

---

## INTRODUCTION

### Background of the Project
Motorcycle owners frequently encounter mechanical problems that are difficult to identify without professional mechanical knowledge or access to a qualified mechanic[cite: 5]. Common symptoms such as difficulty starting, unusual engine sounds, overheating, brake failures, and electrical irregularities may have multiple potential causes, and misdiagnosis can lead to further motorcycle damage or, in critical cases, personal injury[cite: 5]. In many communities, particularly those in rural or semi-urban areas in the Philippines, affordable and readily available motorcycle repair expertise remains limited[cite: 5].

When motorcycle owners resort to searching for repair information online, they often encounter technical content that is not suited to their level of expertise, is not specific to their motorcycle make, model, or year, or fails to clearly communicate when professional repair assistance is urgently required[cite: 5]. This informational gap leaves many owners either performing unsafe do-it-yourself repairs or neglecting motorcycle problems altogether due to uncertainty about the root cause[cite: 5].

To address these concerns, the proposed project will develop a web-based Motorcycle Diagnostic Assistant[cite: 5]. The system will guide users through a structured series of questions about their reported motorcycle symptoms and gather relevant motorcycle details such as make, model, year, and fuel system type[cite: 5]. Based on the collected information, the system will provide possible causes and step-by-step troubleshooting guidance drawn from a curated diagnostic knowledge base[cite: 5]. When configured with an AI provider, the system will generate contextual repair guidance using the Google Gemini AI service[cite: 5]. The system will also issue safety alerts for selected critical symptoms and will support multilingual diagnostic conversations in English, Filipino/Tagalog, and Hiligaynon/Ilonggo[cite: 5]. All diagnostic outputs will be presented as informational support only and will not be treated as confirmed diagnoses or professional mechanical certifications[cite: 5].

### Statement of the Problem or Project Objectives
The main objective of this project will be to design, develop, and evaluate a web-based Motorcycle Diagnostic Assistant that will help users understand common motorcycle symptoms through guided troubleshooting and AI-supported repair guidance[cite: 5].

Specifically, the project will accomplish the following technical objectives:
1. Develop a guided diagnostic workflow that will collect motorcycle details including motorcycle type, make, model, year, variant, engine displacement, and fuel system along with reported symptom information through structured follow-up questions to progressively narrow down possible causes[cite: 5].
2. Build and maintain a structured diagnostic knowledge base containing motorcycle symptoms, associated possible causes, confidence levels, diagnostic tests, expected results, repair instructions, required parts, and safety precautions, accessible to the system's diagnostic engine for offline and AI-augmented responses[cite: 5].
3. Integrate an AI-supported response feature using the Google Gemini API that will use available diagnostic knowledge base records as contextual input to generate clear, accurate, and motorcycle-specific explanations of possible causes and troubleshooting steps[cite: 5].
4. Implement a safety alert mechanism that will detect selected critical-urgency symptoms and immediately advise users to stop operating the motorcycle and seek qualified professional mechanical assistance before any further action is taken[cite: 5].
5. Provide authenticated users with persistent diagnostic conversation history, a conversation staging tracker, and an optional diagnostic photo-upload feature that users may submit alongside symptom descriptions for AI-assisted visual assessment, subject to system and AI provider configuration[cite: 5].
6. Support English, Filipino/Tagalog, and Hiligaynon/Ilonggo in diagnostic questions, system messages, and applicable AI-generated responses to improve accessibility for Filipino motorcycle owners and mechanics[cite: 5].
7. Implement authenticated user access and an AI usage tracking system that will monitor daily API request consumption and token usage against a configurable application budget, supporting controlled and auditable use of the integrated AI provider[cite: 5].
8. Conduct user acceptance testing (UAT) with selected motorcycle owners, riders, and mechanics using representative diagnostic scenarios[cite: 5]. Assess task completion, usability, clarity, language accessibility, and whether predefined critical symptoms produce the expected safety alerts; document test tasks, acceptance criteria, and results[cite: 5].

### Significance of the Project
The proposed system will provide direct practical value to the following beneficiaries[cite: 5]:
* **Motorcycle Owners:** The system will help users systematically describe motorcycle symptoms, respond to guided diagnostic questions, and review possible causes and troubleshooting information in plain, accessible language[cite: 5]. It will reduce reliance on informal and potentially unreliable online sources[cite: 5].
* **Motorcycle Riders:** The safety alert mechanism will notify riders of selected symptoms that indicate serious mechanical risk, helping them make informed decisions about whether to continue riding the motorcycle or seek immediate professional assistance, potentially preventing accidents caused by undetected mechanical failure[cite: 5].
* **Mechanics and Repair Personnel:** The guided diagnostic intake process will encourage motorcycle owners to document their reported symptoms, motorcycle details, and diagnostic observations in a structured format, enabling mechanics to receive more complete and organized problem descriptions when clients seek professional service[cite: 5].
* **Students and Future Researchers:** The project will serve as a reference framework for future studies involving web-based diagnostic systems, guided troubleshooting workflows, AI-augmented information services, and multilingual support in locally contextualized software applications[cite: 5].

### Alignment with Institutional Research Agenda and Sustainable Development Goals
* **Institutional Research Agenda Alignment:** The project will support the institutional research priority related to Information and Communications Technology by developing a web-based application that applies software engineering, AI-supported features, and structured knowledge management to motorcycle diagnostic information for practical community use[cite: 5].
* **Sustainable Development Goal Alignment:**
  * **SDG 9 (Industry, Innovation, and Infrastructure):** The project will apply web technologies, a curated diagnostic knowledge base, and AI integration to create a digital tool that broadens access to motorcycle diagnostic information, particularly for communities with limited access to professional repair expertise[cite: 5].
  * **SDG 3 (Good Health and Well-Being):** The system will include safety-oriented alerts for selected critical motorcycle symptoms and will consistently encourage users to seek qualified professional assistance when appropriate[cite: 5]. The system will not certify motorcycle safety or substitute for a licensed mechanical inspection[cite: 5].

---

## SCOPE AND LIMITATIONS

### System Scope and Technical Architecture

| Component | Description and Coverage |
| :--- | :--- |
| **Core Modules** | The system will include user authentication and registration, guided motorcycle and symptom intake, AI-augmented diagnostic conversations via the Gemini API, a structured diagnostic knowledge base with symptom records and troubleshooting guides, safety alert detection, persistent conversation history with staging and summary, optional diagnostic photo uploads, AI usage tracking, an offline knowledge cache for fallback responses, and an interactive 3D motorcycle component viewer[cite: 5]. |
| **Technology Stack** | The system will use Python and Django for backend processing, SQLite as the default relational database with MySQL available through configuration, and HTML5, CSS3, and JavaScript for the web interface[cite: 5]. Google Gemini is the default AI provider and is accessed through the Google GenAI SDK; a compatible alternative provider may be configured[cite: 5]. The interactive motorcycle viewer uses Three.js[cite: 5]. |
| **Target Users** | The intended users will include motorcycle owners, motorcycle riders, mechanics and repair personnel, and authorized system administrators[cite: 5]. |
| **Deployment** | The system will be accessible through a standard web browser and will require an appropriate local development server or hosted web server environment[cite: 5]. |

### System Boundary and Motorcycle Coverage
The system is designed exclusively for motorcycle troubleshooting, covering symptoms and motorcycle profiles supported by its available diagnostic knowledge base[cite: 5]. Users provide information manually; the system does not connect to motorcycle diagnostic ports, live sensors, or electronic control units (ECUs)[cite: 5]. Its 3D viewer is limited to the motorcycle models and components represented by available model assets[cite: 5].

### Knowledge Sources and Review
Diagnostic guides will identify their source references and review status[cite: 5]. The project will maintain a list of the manufacturer service manuals and other credible technical references actually consulted, and applicable guidance should be reviewed by a qualified mechanic before approval[cite: 5]. An offline cache may retain earlier AI responses; cached responses are not automatically verified repair instructions or a substitute for service manuals[cite: 5].

### Research and Evaluation Plan
Evaluation will use representative diagnostic scenarios with selected motorcycle owners, riders, and mechanics[cite: 5]. Testing will assess task completion, usability, clarity of guidance, language accessibility, and whether predefined critical-symptom cases trigger the expected safety alerts[cite: 5]. Test scenarios and acceptance criteria will be defined before testing, and findings will be reported without claiming that the system replaces professional diagnosis or has been proven to prevent accidents[cite: 5].

### Privacy and Data Handling
Before deployment, the project will document how account information, diagnostic conversations, and uploaded photos are stored and protected; who may access them; applicable retention and deletion procedures; and when submitted content may be sent to an external AI provider[cite: 5]. Users should receive clear notice of this data handling and provider use[cite: 5].

### Limitations
* The reliability of diagnostic guidance depends on the quality, completeness, motorcycle applicability, and review status of available knowledge records[cite: 5]. Only approved and verified troubleshooting guides with recorded sources are used for AI-augmented and offline guide retrieval, while the separate offline answer cache containing prior AI-generated responses is not automatically verified or equivalent to manufacturer service manuals[cite: 5].
* The system's diagnostic coverage will be limited to the symptoms, follow-up questions, and troubleshooting guides available in its knowledge base[cite: 5]. Symptoms not present in the knowledge base may not receive detailed offline guidance[cite: 5].
* AI-generated responses may be incomplete, inaccurate, or not applicable to every motorcycle configuration[cite: 5]. Motorcycle-specific specifications, repair torque values, wiring diagrams, and part compatibility will require verification using appropriate manufacturer service manuals or professional expertise[cite: 5].
* The optional photo-upload and AI-assisted visual assessment feature will depend on whether the selected AI provider and the current system configuration support multimodal image input[cite: 5]. A submitted photo alone will not confirm the cause of a motorcycle problem[cite: 5].
* The system will not connect to motorcycle diagnostic ports, live sensors, or electronic control units[cite: 5]. All diagnostic input will be provided manually by the user through the web interface[cite: 5].
* The interactive 3D viewer will display only the motorcycle components included in its available 3D model assets and will not represent every motorcycle variant, make, or component type[cite: 5].
* The system will not perform repairs, order replacement parts, or provide any assurance that a motorcycle is safe to operate following user-performed maintenance[cite: 5].
* AI service availability will depend on the Google Gemini API configuration, daily application budget limits, and internet connectivity at the time of use[cite: 5].

---

## REFERENCES & TECHNICAL MAPPING

* **Project overview and concept paper:** `README.md`[cite: 5]
* **Django project configuration and app setup:** `mysite/settings.py`[cite: 5]
* **URL routing for dashboard/login/chat endpoints:** `apps/core/urls.py`[cite: 5]
* **Core authentication, dashboard, and chat request handling:** `apps/core/views.py`[cite: 5]
* **Diagnostic logic, safety tripwires, multilingual flow, and guided troubleshooting engine:** `apps/core/diagnostic_engine.py`[cite: 5]
* **Verified motorcycle repair knowledge base and retrieval service:** `apps/motor/knowledge.py`[cite: 5]