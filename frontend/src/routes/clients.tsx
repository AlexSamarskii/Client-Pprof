import { useState } from 'react';
import {
  useClients,
  useCreateClient,
  describeClientProofError,
} from '../hooks/useClientProof';
import { useUser } from '../hooks/useUser';

export function Clients() {
  const { role } = useUser();
  const permitted = role === 'owner' || role === 'admin';
  const clients = useClients(undefined, permitted);
  const create = useCreateClient();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [identity, setIdentity] = useState('');
  const [error, setError] = useState('');
  if (!permitted) return <p role="alert">Доступ не предоставлен.</p>;
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Клиенты</h1>
      <p>
        Клиент входит через свой аккаунт Supabase. Его идентификатор
        предоставляется администратором тестового или рабочего Auth. Запись
        клиента не создаёт участника агентства.
      </p>
      <form
        className="grid gap-2 max-w-lg"
        onSubmit={(e) => {
          e.preventDefault();
          setError('');
          void create
            .mutateAsync({
              display_name: name,
              email,
              external_auth_user_id: identity,
            })
            .then(() => {
              setName('');
              setEmail('');
              setIdentity('');
            })
            .catch((e) => setError(describeClientProofError(e)));
        }}
      >
        <label htmlFor="client-name">Имя клиента</label>
        <input
          className="border p-2"
          id="client-name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label htmlFor="client-email">Электронная почта клиента</label>
        <input
          className="border p-2"
          id="client-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label htmlFor="client-auth-id">Идентификатор клиента в Auth</label>
        <input
          className="border p-2"
          id="client-auth-id"
          required
          value={identity}
          onChange={(e) => setIdentity(e.target.value)}
        />
        <button disabled={create.isPending}>Добавить клиента</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {create.isSuccess ? <p role="status">Клиент добавлен.</p> : null}
      {clients.isPending ? <p role="status">Загрузка клиентов…</p> : null}
      {clients.error ? (
        <p role="alert">{describeClientProofError(clients.error)}</p>
      ) : null}
      <ul>
        {(clients.data ?? []).map((client) => (
          <li key={client.id}>
            {client.display_name} — {client.email}
          </li>
        ))}
      </ul>
    </div>
  );
}
