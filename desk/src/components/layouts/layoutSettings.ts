import LucideBookOpen from "~icons/lucide/book-open";
import LucideContact2 from "~icons/lucide/contact-2";
import LucideMail from "~icons/lucide/mail";
import LucideTicket from "~icons/lucide/ticket";
import { OrganizationsIcon } from "../icons";
import PhoneIcon from "../icons/PhoneIcon.vue";
import { __ } from "@/translation";
import { showComposeEmailModal } from "@/pages/ticket/modalStates";

export const agentPortalSidebarOptions = [
  {
    label: __("Tickets"),
    icon: LucideTicket,
    to: "TicketsAgent",
  },
  {
    label: __("Compose Email"),
    icon: LucideMail,
    onClick: () => {
      showComposeEmailModal.value = true;
    },
  },
  {
    label: __("Knowledge Base"),
    icon: LucideBookOpen,
    to: "AgentKnowledgeBase",
  },
  {
    label: __("Canned Responses"),
    icon: LucideCloudLightning,
    to: "CannedResponses",
  },
  {
    label: __("Customers"),
    icon: OrganizationsIcon,
    to: "CustomerList",
  },
  {
    label: __("Contacts"),
    icon: LucideContact2,
    to: "ContactList",
  },
  {
    label: __("Call Logs"),
    icon: PhoneIcon,
    to: "CallLogs",
  },
];

export const customerPortalSidebarOptions = [
  {
    label: __("Tickets"),
    icon: LucideTicket,
    to: "TicketsCustomer",
  },
  {
    label: __("Knowledge Base"),
    icon: LucideBookOpen,
    to: "CustomerKnowledgeBase",
  },
];
