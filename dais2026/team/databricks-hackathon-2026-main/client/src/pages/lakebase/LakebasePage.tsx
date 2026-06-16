import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Button,
  Input,
  Skeleton,
  Badge,
} from '@databricks/appkit-ui/react';
import { useState, useEffect } from 'react';
import { Check, X, Database } from 'lucide-react';

interface Todo {
  id: number;
  title: string;
  completed: boolean;
  created_at: string;
}

export function LakebasePage() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [newTitle, setNewTitle] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch('/api/lakebase/todos')
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch list: ${res.statusText}`);
        return res.json() as Promise<Todo[]>;
      })
      .then(setTodos)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load list'))
      .finally(() => setLoading(false));
  }, []);

  const addTodo = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;

    setSubmitting(true);
    try {
      const res = await fetch('/api/lakebase/todos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(`Failed to add item: ${res.statusText}`);
      const created = (await res.json()) as Todo;
      setTodos((prev) => [created, ...prev]);
      setNewTitle('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add item');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleTodo = async (id: number) => {
    try {
      const res = await fetch(`/api/lakebase/todos/${id}`, { method: 'PATCH' });
      if (!res.ok) throw new Error(`Failed to update item: ${res.statusText}`);
      const updated = (await res.json()) as Todo;
      setTodos((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update item');
    }
  };

  const deleteTodo = async (id: number) => {
    try {
      const res = await fetch(`/api/lakebase/todos/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Failed to delete item: ${res.statusText}`);
      setTodos((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete item');
    }
  };

  const completedCount = todos.filter((t) => t.completed).length;

  return (
    <div className="max-w-2xl mx-auto px-4 md:px-6 py-8 space-y-5">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" /> Outreach Worklist
        </h2>
        <p className="text-sm text-muted-foreground">
          A shared facility-outreach checklist persisted in Databricks Lakebase (Postgres).
        </p>
      </div>

      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between gap-2">
          <div>
            <CardTitle>What needs following up today?</CardTitle>
            <CardDescription>Add outreach items, check them off as you go.</CardDescription>
          </div>
          {todos.length > 0 && (
            <Badge variant="secondary">
              {completedCount}/{todos.length} done
            </Badge>
          )}
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void addTodo(e)} className="flex gap-2 mb-6">
            <Input
              placeholder="e.g. Email Aravind Eye Hospital about partnership"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              disabled={submitting}
              className="flex-1"
            />
            <Button type="submit" disabled={submitting || !newTitle.trim()}>
              {submitting ? 'Adding…' : 'Add'}
            </Button>
          </form>

          {error && <div className="text-destructive bg-destructive/10 p-3 rounded-md mb-4">{error}</div>}

          {loading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }, (_, i) => (
                <div key={`skeleton-${i}`} className="flex items-center gap-3">
                  <Skeleton className="h-5 w-5 rounded" />
                  <Skeleton className="h-4 flex-1" />
                </div>
              ))}
            </div>
          )}

          {!loading && todos.length === 0 && (
            <p className="text-muted-foreground text-center py-8">
              Nothing on the list yet. Add the first outreach item above.
            </p>
          )}

          {!loading && todos.length > 0 && (
            <div className="space-y-2">
              {todos.map((todo) => (
                <div
                  key={todo.id}
                  className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <button
                    type="button"
                    onClick={() => void toggleTodo(todo.id)}
                    className={`h-5 w-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                      todo.completed
                        ? 'bg-primary border-primary text-primary-foreground'
                        : 'border-muted-foreground/30 hover:border-primary'
                    }`}
                    aria-label={todo.completed ? 'Mark as not done' : 'Mark as done'}
                  >
                    {todo.completed && <Check className="h-3 w-3" />}
                  </button>

                  <span className={`flex-1 ${todo.completed ? 'line-through text-muted-foreground' : ''}`}>
                    {todo.title}
                  </span>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void deleteTodo(todo.id)}
                    className="text-muted-foreground hover:text-destructive shrink-0"
                    aria-label="Delete item"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
