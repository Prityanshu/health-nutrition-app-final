/**
 * Minimal markdown -> HTML for AI-generated content.
 *
 * Shared by the chat view and ChefGenius so there is one implementation
 * rather than two that drift apart.
 *
 * Patterns are anchored per line and greedy. An earlier version used lazy
 * quantifiers like /### (.*?)/g - a lazy group matches the empty string, so it
 * stripped the "###" and threw the heading text away, which is why headings
 * rendered as a bare "#".
 *
 * Input is HTML-escaped first: this content is model-generated and gets
 * injected via dangerouslySetInnerHTML, so it must not be trusted as markup.
 */
export function renderMarkdown(text) {
  if (!text) return '';

  const escaped = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  function inline(s) {
    return s
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>')
      .replace(/`([^`]+?)`/g, '<code>$1</code>');
  }

  return escaped
    .split('\n')
    .map((line) => {
      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        const level = Math.min(heading[1].length, 3);
        return `<h${level}>${inline(heading[2])}</h${level}>`;
      }

      const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
      if (bullet) return `<li>${inline(bullet[1])}</li>`;

      const numbered = line.match(/^\s*(\d+)\.\s+(.*)$/);
      if (numbered) return `<li>${numbered[1]}. ${inline(numbered[2])}</li>`;

      if (line.trim() === '') return '';
      return `<p>${inline(line)}</p>`;
    })
    .filter(Boolean)
    .join('');
}

export default renderMarkdown;
