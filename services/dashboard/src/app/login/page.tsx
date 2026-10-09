import LoginForm from '@/components/LoginForm';
import Card from '@/components/ui/Card';

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  return (
    <main className="mx-auto mt-24 max-w-sm p-6">
      <Card title="Sign in to Auspex">
        <LoginForm next={typeof next === 'string' ? next : '/'} />
      </Card>
    </main>
  );
}
