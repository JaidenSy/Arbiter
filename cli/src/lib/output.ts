import chalk from 'chalk'
import Table from 'cli-table3'

export function printTable(headers: string[], rows: string[][]): void {
  const table = new Table({
    head: headers.map((h) => chalk.bold.cyan(h)),
    style: { border: ['grey'], head: [] },
  })

  for (const row of rows) {
    table.push(row)
  }

  console.log(table.toString())
}

export function printSuccess(msg: string): void {
  console.log(chalk.green('✓') + '  ' + msg)
}

export function printError(msg: string): never {
  console.error(chalk.red('✗') + '  ' + msg)
  process.exit(1)
}

export function printWarning(msg: string): void {
  console.warn(chalk.yellow('⚠') + '  ' + msg)
}
