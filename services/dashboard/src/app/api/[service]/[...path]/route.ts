import { forward } from '@/lib/bff';

export const dynamic = 'force-dynamic';

interface Context {
  params: Promise<{ service: string; path: string[] }>;
}

async function handle(request: Request, { params }: Context): Promise<Response> {
  const { service, path } = await params;
  return forward(service, path, request);
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
