import { Link } from "react-router-dom";
import { Button, EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg p-10">
      <EmptyState title="Страница не найдена" description="Проверьте адрес или вернитесь в кабинет." action={<Link to="/app"><Button size="sm">В кабинет</Button></Link>} />
    </div>
  );
}
