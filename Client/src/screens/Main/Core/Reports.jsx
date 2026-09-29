
const changes = [
  {
    impact: 'High Impact',
    color: 'text-(--accent) bg-red-100',
    date: '2 days ago',
    title:
      'Notion: AI Unbundling + 25% Enterprise Price Increase',
    description:
      'Separated AI features into $10/user add-on tier. Enterprise jumped from $20 to $25/user. This validates separate AI pricing while capturing more from high-value customers.',
  },
  {
    impact: 'High Impact',
    color: 'text-(--accent) bg-red-100',
    date: '3 days ago',
    title: 'Monday.com: Repositioning as "Work Platform"',
    description:
      'Shifted from "Work OS" to "Work Platform for Any Workflow." New homepage emphasizes enterprise scalability and custom app building. More Fortune 500 logos featured.',
  },
  {
    impact: 'Medium Impact',
    color: 'bg-yellow-100 text-[#d4a500]',
    date: '5 days ago',
    title: 'Airtable: Connected Apps Launch',
    description:
      'New low-code app framework for building custom interfaces. Platform play to compete with full custom development alternatives.',
  },
]

const actions = [
  {
    title: '1. Pricing Strategy Workshop',
    description:
      'Schedule a pricing review meeting. Analyze bundled vs. unbundled AI economics. Survey customers on AI usage and willingness to pay separately. Decision needed by end of Q1.',
  },
  {
    title: '2. Update Competitive Materials',
    description:
      'Refresh sales battlecards with new pricing structures and positioning shifts. Train sales team on how to position against unbundled AI offerings and enterprise platform plays.',
  },
  {
    title: '3. Platform Strategy Review',
    description:
      "Airtable's Connected Apps shows extensibility is critical. Review Q2 roadmap for API improvements and developer tools. Consider app marketplace as growth lever.",
  },
]

function Reports() {
  return (
    <div className="px-4 py-6 sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-6xl">
        {/* Header */}
        <div className="mb-8 rounded-2xl bg-(--primary) p-5 shadow sm:p-8 lg:p-12">
          <p className="text-sm text-(--border)">
            Weekly Intelligence Report • Jan 28 – Feb 4, 2026
          </p>
          <h1 className="mt-2 font-[Inter] tracking-tight text-2xl font-bold text-white sm:text-3xl">
            Your Competitors Made 22 Meaningful Changes
          </h1>
          <p className="text-gray-300 mt-3">
            This week saw significant pricing strategy shifts from Notion and Monday.com, plus a major product launch from Airtable. The trend: unbundling AI features and doubling down on enterprise positioning. Here's what you need to know.
          </p>

          <div className="mt-4 flex flex-wrap gap-3">
            <button className="bg-gray-100 hover:bg-gray-200 px-4 py-2 rounded-lg text-sm">
              📥 Download PDF
            </button>
            <button className="bg-gray-100 hover:bg-gray-200 px-4 py-2 rounded-lg text-sm">
              📧 Email Report
            </button>
          </div>
        </div>

        {/* Changes */}
        <h2 className="text-xl font-semibold mb-4">
          Top Competitor Moves
        </h2>

        <div className="space-y-6">
          {changes.map((item, index) => (
            <div key={index} className="bg-white rounded-2xl shadow p-6">
              <div className="mb-3">
                <div className="flex items-center gap-2 text-sm mb-2">
                  <span
                    className={`px-2 py-1 rounded-full ${item.color}`}
                  >
                    {item.impact}
                  </span>
                  <span className="text-(--text-light)">{item.date}</span>
                </div>
                <h3 className="text-lg font-semibold">{item.title}</h3>
              </div>
              <p className="text-(--text-light) text-sm">{item.description}</p>
            </div>
          ))}
        </div>

        {/* Actions */}
        <h2 className="text-xl font-semibold mt-10 mb-4">
          What You Should Do
        </h2>

        <div className="space-y-4">
          {actions.map((action, index) => (
            <div key={index} className="border-l-4 border-(--accent) rounded-2xl shadow p-5">
              <h3 className="font-semibold">
                {action.title}
              </h3>
              <p className="text-(--text-light) text-sm mt-1">
                {action.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default Reports
