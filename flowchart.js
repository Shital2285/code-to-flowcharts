async function generateFlowchart() {
  const code = document.getElementById('code').value;
  const div = document.getElementById('flowchart');
  div.innerHTML = '<p>Generating...</p>';

  try {
    const response = await fetch('/generate_mermaid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const data = await response.json();
    if (!data.mermaid_syntax) {
      div.innerHTML = '<p style="color:red;">No flowchart returned.</p>';
      return;
    }

    // Generate a unique ID for the diagram
    const diagramId = 'flowchartDiagram_' + Date.now();

    // Use mermaidAPI.render
    mermaid.mermaidAPI.render(diagramId, data.mermaid_syntax, (svgCode) => {
      div.innerHTML = svgCode;
    });

  } catch (err) {
    console.error('Flowchart error:', err);
    div.innerHTML = `<p style="color:red;">❌ Error: ${err.message}</p>`;
  }
}
