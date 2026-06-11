import { InstrumentDashboard } from "@/components/dashboard/InstrumentDashboard";

type PageProps = {
  params: Promise<{ symbol: string }>;
};

export default async function InstrumentPage({ params }: PageProps) {
  const { symbol } = await params;

  return <InstrumentDashboard symbol={symbol.toUpperCase()} />;
}
