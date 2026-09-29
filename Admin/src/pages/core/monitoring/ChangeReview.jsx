import Button from '../../../components/ui/Button.jsx';

function ChangeReview() {
  const changes = [
    {
      severity: 'High',
      title: 'Pricing restructure detected',
      domain: 'notion.so/pricing',
      workspace: 'Acme Corp',
      score: 9.1,
      description: 'Detected plan pricing increase and AI add-on separation.',
      removed: 'Business: $18/user/month, AI included',
      added: 'Business: $20/user/month + AI Add-on $10/user/month',
    },
    {
      severity: 'Medium',
      title: 'Homepage positioning update',
      domain: 'monday.com',
      workspace: 'Acme Corp',
      score: 6.8,
      description: 'Hero copy changed from operational workflow language to enterprise platform language.',
      removed: 'Work OS for teams',
      added: 'Work platform for any workflow',
    },
  ];

  return (
    <div className="p-10 space-y-8">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="font-['DM_Serif_Display'] text-4xl font-bold text-(--primary) mb-2">
            Change Review
          </h1>
          <p className="text-(--text-light) text-base max-w-2xl">
            Internal moderation/QA screen for meaningful changes before AI insight generation or customer-facing surfacing.
          </p>
        </div>
        <Button title="Approve All Safe" variant="secondary" />
      </div>

      {/* Review Cards */}
      <div className="space-y-4">
        {changes.map((change, idx) => (
          <div key={idx} className="bg-white border border-(--border) rounded-lg p-6">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`inline-block px-2 py-1 text-xs font-bold rounded ${
                    change.severity === 'High'
                      ? 'bg-red-50 text-red-600'
                      : change.severity === 'Medium'
                      ? 'bg-yellow-50 text-yellow-600'
                      : 'bg-blue-50 text-blue-600'
                  }`}>
                    {change.severity} Severity
                  </span>
                </div>
                <h3 className="text-lg font-bold text-(--primary) mb-2">{change.title}</h3>
                <p className="text-sm text-(--text-light)">
                  {change.domain} • {change.workspace} • score {change.score}/10
                </p>
              </div>
              <div className="flex gap-2 ml-4">
                <Button title="Approve AI" variant="primary" />
                <Button title="Mark Noise" variant="secondary" />
              </div>
            </div>

            <p className="text-(--text) mb-4">{change.description}</p>

            <div className="bg-(--bg) rounded-lg p-4 space-y-2">
              <div className="text-sm">
                <span className="line-through text-red-600">{change.removed}</span>
              </div>
              <div className="text-sm text-green-600">
                <span className="bg-green-50 px-1 rounded">{change.added}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ChangeReview;
