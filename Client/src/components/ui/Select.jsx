import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

function Select({
	id,
	value,
	onChange,
	options = [],
	placeholder = 'Select an option',
	disabled = false,
	fullWidth = true,
	className = '',
	style = {},
	name,
	required = false,
	...rest
}) {
	const [isOpen, setIsOpen] = useState(false);
	const [isFocused, setIsFocused] = useState(false);
	const [activeIndex, setActiveIndex] = useState(-1);
	const containerRef = useRef(null);

	const normalizedOptions = useMemo(() => {
		return options.map((option, index) => {
			if (typeof option === 'object' && option !== null) {
				const optionValue = option.value ?? option.id ?? '';
				const optionLabel = option.label ?? option.name ?? String(optionValue);
				return {
					value: optionValue,
					label: optionLabel,
					disabled: Boolean(option.disabled),
					key: String(optionValue || index),
				};
			}

			return {
				value: option,
				label: String(option),
				disabled: false,
				key: String(option),
			};
		});
	}, [options]);

	const selectedOption = useMemo(() => {
		return normalizedOptions.find((option) => String(option.value) === String(value));
	}, [normalizedOptions, value]);

	useEffect(() => {
		const onClickOutside = (event) => {
			if (containerRef.current && !containerRef.current.contains(event.target)) {
				setIsOpen(false);
				setIsFocused(false);
			}
		};

		const onEscape = (event) => {
			if (event.key === 'Escape') {
				setIsOpen(false);
				setIsFocused(false);
			}
		};

		document.addEventListener('mousedown', onClickOutside);
		document.addEventListener('keydown', onEscape);

		return () => {
			document.removeEventListener('mousedown', onClickOutside);
			document.removeEventListener('keydown', onEscape);
		};
	}, []);

	const emitChange = (nextValue) => {
		if (!onChange) return;
		onChange({
			target: {
				id,
				name: name || id,
				value: nextValue,
			},
		});
	};

	const selectOption = (option) => {
		if (option.disabled) return;
		emitChange(option.value);
		setIsOpen(false);
		setIsFocused(false);
	};

	const handleKeyDown = (event) => {
		if (disabled) return;

		if (!isOpen && (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown')) {
			event.preventDefault();
			setIsOpen(true);
			const selectedIndex = normalizedOptions.findIndex((option) => String(option.value) === String(value));
			setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
			return;
		}

		if (!isOpen) return;

		if (event.key === 'ArrowDown') {
			event.preventDefault();
			setActiveIndex((prev) => {
				const next = prev < normalizedOptions.length - 1 ? prev + 1 : 0;
				return next;
			});
		}

		if (event.key === 'ArrowUp') {
			event.preventDefault();
			setActiveIndex((prev) => {
				const next = prev > 0 ? prev - 1 : normalizedOptions.length - 1;
				return next;
			});
		}

		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			const option = normalizedOptions[activeIndex];
			if (option) selectOption(option);
		}
		if (event.key === 'Tab') {
			setIsOpen(false);
		}
	};

	const selectStyles = {
		width: fullWidth ? '100%' : 'auto',
		minHeight: '44px',
		padding: '12px 40px 12px 14px',
		borderRadius: 'var(--radius-sm)',
		fontSize: '14px',
		lineHeight: '1.4',
		fontFamily: 'var(--font-body)',
		color: 'var(--text)',
		backgroundColor: 'var(--card)',
		border: isFocused ? '1px solid var(--accent)' : '1px solid var(--border)',
		boxShadow: isFocused
			? '0 0 0 3px rgba(255, 107, 107, 0.16)'
			: '0 1px 2px rgba(0, 0, 0, 0.04)',
		transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
		outline: 'none',
		cursor: disabled ? 'not-allowed' : 'pointer',
		opacity: disabled ? '0.7' : '1',
		...style,
	};

	return (
		<div ref={containerRef} className={`relative ${fullWidth ? 'w-full' : 'w-auto'} ${className}`}>
			<button
				type="button"
				id={id}
				name={name || id}
				disabled={disabled}
				required={required}
				style={selectStyles}
				className="text-left"
				aria-disabled={disabled}
				aria-expanded={isOpen}
				aria-haspopup="listbox"
				onFocus={() => setIsFocused(true)}
				onBlur={() => setIsFocused(false)}
				onClick={() => {
					if (disabled) return;
					setIsOpen((prev) => !prev);
					const selectedIndex = normalizedOptions.findIndex((option) => String(option.value) === String(value));
					setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
				}}
				onKeyDown={handleKeyDown}
				{...rest}
			>
				<span className={`${selectedOption ? 'text-(--text)' : 'text-(--text-light)'}`}>
					{selectedOption ? selectedOption.label : placeholder}
				</span>
			</button>

			<span className={`pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-(--text-light) transition-transform ${isOpen ? 'rotate-180' : ''}`}>
				<ChevronDown size={16} />
			</span>

			{isOpen && (
				<div
					className="absolute z-40 mt-2 max-h-64 w-full overflow-auto rounded-xl border border-(--border) bg-white p-1 shadow-lg"
					role="listbox"
				>
					{normalizedOptions.length === 0 && (
						<div className="px-3 py-2 text-sm text-(--text-light)">No options</div>
					)}

					{normalizedOptions.map((option, index) => {
						const isSelected = String(option.value) === String(value);
						const isActive = index === activeIndex;

						return (
							<button
								type="button"
								key={option.key}
								disabled={option.disabled}
								role="option"
								aria-selected={isSelected}
								onMouseEnter={() => setActiveIndex(index)}
								onClick={() => selectOption(option)}
								className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
									option.disabled
										? 'cursor-not-allowed text-slate-400 opacity-60'
										: isSelected
											? 'bg-[rgba(78,205,196,0.18)] text-(--primary)'
											: isActive
												? 'bg-[rgba(255,107,107,0.12)] text-(--text)'
												: 'text-(--text) hover:bg-[rgba(255,107,107,0.1)]'
								}`}
							>
								<span>{option.label}</span>
								{isSelected && <Check size={14} className="text-(--primary)" />}
							</button>
						);
					})}
				</div>
			)}
		</div>
	);
}

export default Select;
