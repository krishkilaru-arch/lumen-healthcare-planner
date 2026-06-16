import { GenieChat, Badge } from '@databricks/appkit-ui/react';
import { Sparkles } from 'lucide-react';

const EXAMPLES = [
  'How many facilities are there in total?',
  'Which cities have the most facilities?',
  'What are the most common medical specialties?',
  'List the 10 largest facilities by bed capacity',
];

export function GeniePage() {
  return (
    <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 space-y-5">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" /> Ask Genie
        </h2>
        <p className="text-sm text-muted-foreground">
          Natural-language questions about the Virtue Foundation healthcare facilities, answered with governed SQL by
          Databricks AI/BI Genie.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-muted-foreground self-center mr-1">Try asking:</span>
        {EXAMPLES.map((q) => (
          <Badge key={q} variant="secondary" className="font-normal">
            {q}
          </Badge>
        ))}
      </div>

      <div className="h-[min(620px,72vh)] border rounded-xl overflow-hidden bg-card">
        <GenieChat alias="default" placeholder="Ask a question about the data…" />
      </div>
    </div>
  );
}
