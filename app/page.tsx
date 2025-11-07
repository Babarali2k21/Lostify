import { createClient } from '@/lib/supabase/server';

export default async function Home() {
  const supabase = await createClient();
  const { data: instruments } = await supabase.from("instruments").select();
  console.log(instruments);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <h1 className="text-4xl font-bold">Welcome to Lostify!</h1>
      <ul>
        {instruments.map((instrument) => (
          <li key={instrument.id}>{instrument.name}</li>
        ))}
      </ul>
    </div>
  );
}