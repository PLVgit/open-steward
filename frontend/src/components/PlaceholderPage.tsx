import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface PlaceholderPageProps {
  title: string;
  description: string;
  ticket: string;
}

/** A stub page for features arriving in a later ticket. */
export function PlaceholderPage({ title, description, ticket }: PlaceholderPageProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          This view is a placeholder. It will be implemented in {ticket}.
        </p>
      </CardContent>
    </Card>
  );
}
