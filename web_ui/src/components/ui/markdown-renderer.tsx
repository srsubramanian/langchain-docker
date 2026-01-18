import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter, type SyntaxHighlighterProps } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '@/lib/cn';
import { Copy, Check } from 'lucide-react';
import { useState, useCallback } from 'react';

// Type assertion for the style prop
type StyleProp = SyntaxHighlighterProps['style'];

interface MarkdownRendererProps {
  content: string;
  className?: string;
  /** Use compact styling for chat messages */
  compact?: boolean;
  /** Force light or dark theme, or auto-detect from system */
  theme?: 'light' | 'dark' | 'auto';
}

// Detect if dark mode is active
function useIsDarkMode(): boolean {
  if (typeof window === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

// Copy button for code blocks
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded bg-muted/80 hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
      title="Copy code"
    >
      {copied ? (
        <Check className="h-4 w-4 text-green-500" />
      ) : (
        <Copy className="h-4 w-4 text-muted-foreground" />
      )}
    </button>
  );
}

export function MarkdownRenderer({
  content,
  className,
  compact = false,
  theme = 'auto',
}: MarkdownRendererProps) {
  const systemDark = useIsDarkMode();
  const isDark = theme === 'auto' ? systemDark : theme === 'dark';

  const proseClasses = compact
    ? 'prose prose-sm dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-xs max-w-none'
    : 'prose prose-slate dark:prose-invert prose-pre:p-0 prose-pre:bg-transparent max-w-none';

  return (
    <div className={cn(proseClasses, className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code block with syntax highlighting
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';
            const codeString = String(children).replace(/\n$/, '');

            // Check if this is an inline code or a block
            const isInline = !match && !codeString.includes('\n');

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-muted text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            return (
              <div className="relative group my-4 rounded-lg overflow-hidden">
                {language && (
                  <div className="absolute top-0 left-0 px-3 py-1 text-xs font-medium text-muted-foreground bg-muted/50 rounded-br">
                    {language}
                  </div>
                )}
                <CopyButton code={codeString} />
                <SyntaxHighlighter
                  style={(isDark ? oneDark : oneLight) as StyleProp}
                  language={language || 'text'}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: '0.5rem',
                    fontSize: '0.875rem',
                    padding: language ? '2.5rem 1rem 1rem' : '1rem',
                  }}
                >
                  {codeString}
                </SyntaxHighlighter>
              </div>
            );
          },
          // Enhanced table styling
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto rounded-lg border">
                <table className="min-w-full divide-y divide-border">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="px-4 py-2 text-left text-sm font-semibold bg-muted">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="px-4 py-2 text-sm border-t">
                {children}
              </td>
            );
          },
          // Enhanced blockquote
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-primary/30 pl-4 italic text-muted-foreground my-4">
                {children}
              </blockquote>
            );
          },
          // Links open in new tab
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
