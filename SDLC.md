# SDLC report section

## SDLC Model Used: Agile-inspired Iterative Incremental Model

InboxIQ was developed using an iterative and incremental SDLC approach. This model was suitable because the system evolved in multiple stages rather than being built in a fixed linear sequence. The project began with a basic user interface, followed by Gmail integration, OAuth authentication, ML-based email classification, AI reply generation, deployment, progressive email loading, and UI refinement. Each stage added a working feature and exposed new issues that were corrected in the next iteration.

This approach was effective because both requirements and implementation details changed during development. For example, the frontend moved from Streamlit to HTML, CSS, and JavaScript, the authentication flow was redesigned, backend structure was reorganized, and the email loading logic was improved from a single large fetch to progressive batch loading. These changes would not fit a strict Waterfall model, since design decisions and feature scope continued to evolve during implementation.

The iterative incremental model allowed continuous testing, debugging, deployment, and refinement of both the backend system and the ML pipeline. As a result, the project improved step by step while remaining functional throughout development.
