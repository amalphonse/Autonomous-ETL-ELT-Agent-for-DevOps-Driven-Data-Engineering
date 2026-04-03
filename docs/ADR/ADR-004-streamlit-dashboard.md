# ADR-004: Streamlit for Interactive Dashboard

**Status**: Accepted

**Date**: April 2026

## Context

The project needs an interactive web UI for users to:
- Submit user stories (ETL requirements)
- View execution results and generated code
- Browse execution history
- Analyze pipeline metrics and lineage

We need rapid UI development without maintaining separate frontend/backend code.

## Decision

**Use Streamlit for the interactive dashboard.**

Streamlit provides:
- **Python-First Development**: Write UI in pure Python
- **Rapid Prototyping**: Changes reflect instantly (hot reload)
- **Built-In Components**: Charts, forms, data tables out-of-the-box
- **No JavaScript Required**: Focus on backend logic
- **Easy Deployment**: Simple containerization

## Rationale

1. **Fast Time-to-Market**: Build UI in hours, not weeks
2. **No DevOps Complexity**: No separate frontend build process
3. **Data Science Focus**: Designed for data-centric applications
4. **Interactive Widgets**: Built-in charts, metrics, forms
5. **Community Templates**: Rich ecosystem of examples

### Trade-offs

- **Architecture**: Single-threaded re-run model (not ideal for highly interactive apps)
- **Styling**: Limited customization vs. React/Vue
- **Large Data**: Streaming updates harder than traditional frameworks
- **Caching**: Must manage state carefully to avoid re-computation

## Consequences

**Positive**:
- Reduced development time (from weeks to days)
- No frontend/backend disconnect
- Easy for data engineers to modify
- Great for demos and internal tools
- Rapid iteration based on user feedback

**Negative**:
- Reset-on-interaction model (page reloads on button click)
- Performance limitations with large datasets
- Limited advanced UI features
- Server-side rendering (no offline use)

## Alternatives Considered

1. **React/TypeScript Frontend**:
   - Pros: Full control, rich ecosystem, performant
   - Cons: Requires JS expertise, longer development time, separate CI/CD

2. **Dash (by Plotly)**:
   - Pros: More flexibility than Streamlit, callbacks
   - Cons: More boilerplate, steeper learning curve

3. **Flask + Jinja2**:
   - Pros: Full control, lightweight
   - Cons: Manual HTML/CSS, more development needed

## Design Patterns

- **Tab-Based Navigation**: Separate concerns (Submit, History, Analytics, Lineage)
- **Sidebar Configuration**: API URL selection, health checks
- **Expanders**: Hide/show detailed agent outputs
- **Session State**: Cache execution results during user session

## Performance Considerations

- Implemented `/pipelines/demo` endpoint for instant results (not waiting for LLM)
- Client-side caching in browser for pagination
- Lazy loading of large result sections

## Future Improvements

- Host on Streamlit Cloud for easy sharing
- Add user authentication for multi-tenant support
- Implement WebSocket for real-time execution progress
- Add custom CSS theming for enterprise deployments
