/** The one error body every dashboard API route returns. */
export interface ErrorBody {
  error: {
    code: string;
    message: string;
    upstream_status: number | null;
  };
}

export function errorResponse(
  status: number,
  code: string,
  message: string,
  upstreamStatus: number | null = null,
): Response {
  const body: ErrorBody = { error: { code, message, upstream_status: upstreamStatus } };
  return Response.json(body, { status });
}
