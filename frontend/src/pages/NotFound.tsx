import { Link } from "react-router-dom";
import { EmptyState, buttonClass } from "../components/ui";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg p-10">
      <EmptyState title="Страница не найдена" description="Проверьте адрес или вернитесь в кабинет." action={<Link to="/app" className={buttonClass("primary", "sm")}>В кабинет</Link>} />
    </div>
  );
}
