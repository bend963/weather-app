import { HistoryView } from "@/components/HistoryView";

export default async function HistoryPage({ params }: { params: Promise<{ locationId: string }> }) {
  const { locationId } = await params;
  return <HistoryView locationId={locationId} />;
}
